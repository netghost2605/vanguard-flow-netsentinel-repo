"""
speedtest_agent.py  –  Headless network monitoring agent
=========================================================
Drop this file + speedtest.exe on any Windows/Linux/Mac machine.
It runs speed tests and DNS checks on a schedule and exposes the
results over a simple HTTP JSON API so the main Network Monitor
console can pull data from it remotely.

Usage
-----
  python speedtest_agent.py                  # defaults
  python speedtest_agent.py --port 7331      # custom port
  python speedtest_agent.py --interval 10    # test every 10 min
  python speedtest_agent.py --host 0.0.0.0   # bind all interfaces

API endpoints
-------------
  GET  /info      hostname, IP, version, uptime, config
  GET  /status    latest single reading (dl, ul, ping, dns)
  GET  /data      full history (same JSON schema as the console)
  POST /run       trigger an immediate speed test
  POST /dns       trigger an immediate DNS check
  GET  /health    simple liveness probe  →  {"ok": true}

Config file
-----------
  speedtest_agent_config.json  (created next to this script on first run)
  Keys: port, interval_minutes, speedtest_path, bind_host, token
  If token is set, clients must send  Authorization: Bearer <token>
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── Resolve paths ─────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent

if getattr(sys, 'frozen', False):
    HERE = Path(sys.executable).parent

CONFIG_FILE = str(HERE / 'speedtest_agent_config.json')
DATA_FILE   = str(HERE / 'speedtest_agent_data.json')

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_PORT        = 7331
DEFAULT_INTERVAL    = 5        # minutes
DEFAULT_BIND        = '0.0.0.0'
VERSION             = '1.0.0'

# ── Global state (protected by a single RLock) ────────────────────────────────
_lock        = threading.RLock()
_start_time  = time.time()
_running_test = False
_running_dns  = False

DNS_HOSTS = [
    'google.com', 'cloudflare.com', 'microsoft.com',
    'amazon.com', 'bbc.co.uk', 'github.com',
]

# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────

def _load_config():
    defaults = {
        'port':             DEFAULT_PORT,
        'interval_minutes': DEFAULT_INTERVAL,
        'bind_host':        DEFAULT_BIND,
        'speedtest_path':   '',   # empty = auto-detect
        'token':            '',   # empty = no auth required
    }
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE) as f:
                loaded = json.load(f)
            for k in defaults:
                if k in loaded:
                    defaults[k] = loaded[k]
        except Exception:
            pass
    return defaults


def _save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def _find_speedtest(cfg_path: str) -> str:
    """Return path to speedtest.exe, checking config then common locations."""
    if cfg_path and Path(cfg_path).exists():
        return cfg_path

    candidates = [
        HERE / 'speedtest.exe',
        HERE / 'speedtest',
        Path('speedtest.exe'),
        Path('speedtest'),
    ]
    # Also check PATH
    import shutil
    in_path = shutil.which('speedtest') or shutil.which('speedtest.exe')
    if in_path:
        candidates.insert(0, Path(in_path))

    for c in candidates:
        if c.exists():
            return str(c)

    return str(HERE / 'speedtest.exe')   # fallback — will fail with clear error


# ─────────────────────────────────────────────────────────────────────────────
#  Data persistence
# ─────────────────────────────────────────────────────────────────────────────

def _empty_data():
    return {
        'timestamps':     [],
        'download':       [],
        'upload':         [],
        'ping':           [],
        'dns_timestamps': [],
        'dns_values':     [],
    }


def _load_data():
    if Path(DATA_FILE).exists():
        try:
            with open(DATA_FILE) as f:
                d = json.load(f)
            if not isinstance(d, dict):
                return _empty_data()
            for key in ('timestamps', 'download', 'upload', 'ping',
                        'dns_timestamps', 'dns_values'):
                if not isinstance(d.get(key), list):
                    d[key] = []
            # Cap sizes
            for key in ('timestamps', 'download', 'upload', 'ping'):
                d[key] = d[key][-10000:]
            d['dns_timestamps'] = d['dns_timestamps'][-500:]
            d['dns_values']     = d['dns_values'][-500:]
            # Ensure parallel arrays are same length
            n = min(len(d['timestamps']), len(d['download']),
                    len(d['upload']), len(d['ping']))
            for key in ('timestamps', 'download', 'upload', 'ping'):
                d[key] = d[key][:n]
            n_dns = min(len(d['dns_timestamps']), len(d['dns_values']))
            d['dns_timestamps'] = d['dns_timestamps'][:n_dns]
            d['dns_values']     = d['dns_values'][:n_dns]
            return d
        except Exception:
            pass
    return _empty_data()


def _save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  Speed test
# ─────────────────────────────────────────────────────────────────────────────

def _rx(text, pat):
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        v = m.group(1)
        try:
            return float(v)
        except Exception:
            return None
    return None


def run_speedtest(exe_path: str) -> dict:
    """
    Run speedtest.exe and return {'download': float, 'upload': float,
    'ping': float, 'error': str|None}.
    """
    if not Path(exe_path).exists():
        return {'download': None, 'upload': None, 'ping': None,
                'error': f'speedtest.exe not found at: {exe_path}'}

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    dl = ul = pg = None

    # Attempt 1: JSON
    try:
        r = subprocess.run(
            [exe_path, '--format=json', '--accept-license', '--accept-gdpr'],
            capture_output=True, text=True, timeout=150,
            creationflags=flags)
        if r.returncode == 0:
            st = json.loads(r.stdout.strip())
            if 'bandwidth' in st.get('download', {}):
                dl = round(st['download']['bandwidth'] / 125000, 2)
                ul = round(st['upload']['bandwidth']   / 125000, 2)
                pg = st['ping']['latency']
            elif 'download' in st:
                dl = round(st['download'] / 1e6, 2) if st['download'] > 1000 else float(st['download'])
                ul = round(st['upload']   / 1e6, 2) if st['upload']   > 1000 else float(st['upload'])
                pg = float(st.get('ping', 0))
    except Exception:
        pass

    # Attempt 2: plain text
    if dl is None:
        try:
            r2 = subprocess.run(
                [exe_path, '--accept-license', '--accept-gdpr'],
                capture_output=True, text=True, timeout=150,
                creationflags=flags)
            txt = r2.stdout + r2.stderr
            dl = _rx(txt, r'Download[^:]*:\s*([\d.]+)')
            ul = _rx(txt, r'Upload[^:]*:\s*([\d.]+)')
            pg = _rx(txt, r'(?:Latency|Ping)[^:]*:\s*([\d.]+)')
        except Exception:
            pass

    # Attempt 3: bare run
    if dl is None:
        try:
            r3 = subprocess.run([exe_path], capture_output=True, text=True,
                                timeout=150, creationflags=flags)
            txt3 = r3.stdout + r3.stderr
            dl = _rx(txt3, r'Download[^:]*:\s*([\d.]+)')
            ul = _rx(txt3, r'Upload[^:]*:\s*([\d.]+)')
            pg = _rx(txt3, r'(?:Latency|Ping)[^:]*:\s*([\d.]+)')
        except Exception:
            pass

    if dl is None:
        return {'download': None, 'upload': None, 'ping': None,
                'error': 'All attempts failed – no speed values found'}

    return {
        'download': dl,
        'upload':   ul if ul is not None else 0.0,
        'ping':     pg if pg is not None else 0.0,
        'error':    None,
    }


def run_dns_check() -> dict:
    """Return {'avg_ms': float, 'n_hosts': int, 'error': str|None}."""
    results = []
    for host in DNS_HOSTS:
        try:
            t0 = time.perf_counter()
            socket.getaddrinfo(host, None)
            results.append((time.perf_counter() - t0) * 1000)
        except OSError:
            pass
    if not results:
        return {'avg_ms': None, 'n_hosts': 0,
                'error': 'No DNS hosts responded'}
    return {
        'avg_ms':  round(sum(results) / len(results), 2),
        'n_hosts': len(results),
        'error':   None,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Background workers
# ─────────────────────────────────────────────────────────────────────────────

def _worker_speedtest(cfg):
    global _running_test
    if _running_test:
        return
    _running_test = True
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] Running speed test…', flush=True)

    try:
        exe = _find_speedtest(cfg.get('speedtest_path', ''))
        result = run_speedtest(exe)

        if result['error']:
            print(f'  ✗ {result["error"]}', flush=True)
            return

        with _lock:
            data = _load_data()
            data['timestamps'].append(datetime.now().isoformat())
            data['download'].append(result['download'])
            data['upload'].append(result['upload'])
            data['ping'].append(result['ping'])
            for key in ('timestamps', 'download', 'upload', 'ping'):
                if len(data[key]) > 10000:
                    data[key] = data[key][-10000:]
            _save_data(data)

        print(f'  ✓ DL {result["download"]} Mbps  '
              f'UL {result["upload"]} Mbps  '
              f'Ping {result["ping"]} ms', flush=True)
    finally:
        _running_test = False


def _worker_dns():
    global _running_dns
    if _running_dns:
        return
    _running_dns = True
    try:
        result = run_dns_check()
        if result['error']:
            print(f'  DNS ✗ {result["error"]}', flush=True)
            return

        avg = result['avg_ms']
        with _lock:
            data = _load_data()
            data['dns_timestamps'].append(datetime.now().isoformat())
            data['dns_values'].append(avg)
            if len(data['dns_timestamps']) > 500:
                data['dns_timestamps'] = data['dns_timestamps'][-500:]
                data['dns_values']     = data['dns_values'][-500:]
            _save_data(data)

        print(f'  DNS ✓ {avg:.1f} ms  '
              f'({result["n_hosts"]}/{len(DNS_HOSTS)} hosts)', flush=True)
    finally:
        _running_dns = False


def _schedule_loop(cfg):
    """Run speedtest + DNS check on the configured interval, forever."""
    interval_s = cfg.get('interval_minutes', DEFAULT_INTERVAL) * 60

    # Run once immediately on start
    threading.Thread(target=_worker_speedtest, args=(cfg,), daemon=True).start()
    time.sleep(5)
    threading.Thread(target=_worker_dns, daemon=True).start()

    while True:
        time.sleep(interval_s)
        threading.Thread(target=_worker_speedtest, args=(cfg,), daemon=True).start()
        time.sleep(10)
        threading.Thread(target=_worker_dns, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
#  HTTP API
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_psutil(auto=True, log=print):
    """Make psutil available, installing it if necessary.

    The agent is deployed to remote boxes (often a bare Pi) where nobody wants
    to pip-install by hand. psutil is a compiled extension so it cannot be
    vendored, but it can be fetched once on first run. Everything degrades
    cleanly if that is not possible — the agent still serves, just with less
    system detail.
    """
    try:
        import psutil          # noqa: F401
        return True, 'present'
    except ImportError:
        pass
    if not auto:
        return False, 'missing (auto-install disabled)'
    log('[agent] psutil not found - installing it (one time)...')
    for cmd in ([sys.executable, '-m', 'pip', 'install', '--quiet', 'psutil'],
                [sys.executable, '-m', 'pip', 'install', '--quiet', '--user', 'psutil'],
                [sys.executable, '-m', 'pip', 'install', '--quiet',
                 '--break-system-packages', 'psutil']):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception as e:
            log('[agent] pip failed: %s' % e)
            continue
        if r.returncode == 0:
            # importlib caches the failed import, so clear it before retrying
            try:
                import importlib
                importlib.invalidate_caches()
            except Exception:
                pass
            try:
                import psutil  # noqa: F401
                log('[agent] psutil installed.')
                return True, 'installed on first run'
            except ImportError:
                continue
    log('[agent] Could not install psutil - continuing with reduced detail.')
    log('[agent] Install it manually for CPU/memory/disk/temperature reporting:')
    log('[agent]     %s -m pip install psutil' % sys.executable)
    return False, 'unavailable'


def _sys_facts():
    """Best-effort system detail for /info.

    psutil is optional: the agent often runs on a bare Pi with nothing but the
    standard library, so every psutil field is individually guarded and simply
    omitted when unavailable rather than failing the whole endpoint.
    """
    import platform
    f = {}
    try:
        f['platform'] = platform.platform(terse=True)
        f['machine'] = platform.machine()
        f['processor'] = platform.processor() or platform.machine()
        f['python'] = platform.python_version()
        f['system'] = platform.system()
        f['release'] = platform.release()
    except Exception:
        pass
    try:
        f['cpu_count'] = os.cpu_count()
    except Exception:
        pass
    try:
        f['timezone'] = time.tzname[0]
        f['local_time'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        pass
    try:
        import psutil
        try: f['cpu_percent'] = round(psutil.cpu_percent(interval=0.2), 1)
        except Exception: pass
        try:
            vm = psutil.virtual_memory()
            f['mem_total_mb'] = round(vm.total / 1048576)
            f['mem_used_mb'] = round(vm.used / 1048576)
            f['mem_percent'] = round(vm.percent, 1)
        except Exception: pass
        try:
            du = psutil.disk_usage(os.path.abspath(os.sep))
            f['disk_total_gb'] = round(du.total / 1073741824, 1)
            f['disk_free_gb'] = round(du.free / 1073741824, 1)
            f['disk_percent'] = round(du.percent, 1)
        except Exception: pass
        try: f['boot_time'] = int(psutil.boot_time())
        except Exception: pass
        try:
            f['system_uptime_seconds'] = int(time.time() - psutil.boot_time())
        except Exception: pass
        try:
            temps = psutil.sensors_temperatures() or {}
            for _k, entries in temps.items():
                if entries and entries[0].current:
                    f['temp_c'] = round(entries[0].current, 1)
                    break
        except Exception: pass
        try:
            la = psutil.getloadavg()
            f['load_1m'], f['load_5m'], f['load_15m'] = [round(x, 2) for x in la]
        except Exception: pass
        try:
            nics = []
            stats = psutil.net_if_stats()
            for nic, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if getattr(a.family, 'name', '') == 'AF_INET' and a.address \
                            and not a.address.startswith('127.'):
                        up = getattr(stats.get(nic), 'isup', None)
                        nics.append('%s=%s%s' % (nic, a.address, '' if up else ' (down)'))
                        break
            if nics:
                f['interfaces'] = ', '.join(nics[:4])
        except Exception: pass
    except Exception:
        f['psutil'] = globals().get('_PSUTIL_STATE') or 'not installed'
    else:
        state = globals().get('_PSUTIL_STATE')
        if state and state != 'present':
            f['psutil'] = state
    return f


def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def _make_handler(cfg):
    """Return a request handler class with cfg baked in."""

    token = cfg.get('token', '').strip()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            ts = datetime.now().strftime('%H:%M:%S')
            print(f'[{ts}] {self.address_string()}  {fmt % args}', flush=True)

        def _auth(self):
            if not token:
                return True
            auth = self.headers.get('Authorization', '')
            return auth == f'Bearer {token}'

        def _json(self, code, obj):
            body = json.dumps(obj, indent=2).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)

        def _not_found(self):
            self._json(404, {'error': 'not found'})

        def _unauth(self):
            self._json(401, {'error': 'unauthorized – provide Authorization: Bearer <token>'})

        def _status_snapshot(self, data):
            """Build the /status response from data."""
            dl   = data['download'][-1]  if data['download']  else None
            ul   = data['upload'][-1]    if data['upload']    else None
            pg   = data['ping'][-1]      if data['ping']      else None
            dns  = data['dns_values'][-1] if data['dns_values'] else None
            ts   = data['timestamps'][-1] if data['timestamps'] else None
            dns_ts = data['dns_timestamps'][-1] if data['dns_timestamps'] else None
            snap = {
                'download':      dl,
                'upload':        ul,
                'ping':          pg,
                'dns':           dns,
                'last_test':     ts,
                'last_dns':      dns_ts,
                'timestamp':     ts,
                'running_test':  _running_test,
                'running_dns':   _running_dns,
            }
            # Context for the reading, so the dashboard can show where it came
            # from and how it compares with this agent's own recent history.
            try:
                snap['isp'] = data.get('isp') or ''
                snap['server'] = data.get('server_name') or ''
                snap['samples'] = len(data.get('timestamps') or [])
                snap['last_error'] = data.get('last_error') or ''
                recent = [x for x in (data.get('download') or [])[-10:] if x]
                if recent:
                    snap['avg_download_10'] = round(sum(recent) / len(recent), 1)
                recent_u = [x for x in (data.get('upload') or [])[-10:] if x]
                if recent_u:
                    snap['avg_upload_10'] = round(sum(recent_u) / len(recent_u), 1)
                pings = [x for x in (data.get('ping') or [])[-10:] if x]
                if len(pings) > 1:
                    snap['jitter'] = round(
                        sum(abs(pings[i] - pings[i - 1])
                            for i in range(1, len(pings))) / (len(pings) - 1), 1)
            except Exception:
                pass
            return snap

        def do_GET(self):
            path = self.path.split('?')[0].rstrip('/')

            if path == '/health':
                self._json(200, {'ok': True})
                return

            if not self._auth():
                self._unauth(); return

            if path == '/info':
                uptime_s = int(time.time() - _start_time)
                out = {
                    'hostname':         socket.gethostname(),
                    'ip':               _local_ip(),
                    'version':          VERSION,
                    'uptime_seconds':   uptime_s,
                    'interval_minutes': cfg.get('interval_minutes', DEFAULT_INTERVAL),
                    'port':             cfg.get('port', DEFAULT_PORT),
                    'auth_required':    bool(token),
                }
                # Everything the dashboard needs to describe this box without
                # having to log into it. Unknown keys are rendered generically
                # by the agent detail panel, so adding more here is safe.
                try:
                    out.update(_sys_facts())
                except Exception:
                    pass
                try:
                    with _lock:
                        d = _load_data()
                    out['samples'] = len(d.get('timestamps') or [])
                    out['dns_samples'] = len(d.get('dns_timestamps') or [])
                    if d.get('timestamps'):
                        out['first_sample'] = d['timestamps'][0]
                    out['isp'] = d.get('isp') or ''
                    out['server_name'] = d.get('server_name') or ''
                except Exception:
                    pass
                try:
                    out['speedtest_exe'] = cfg.get('speedtest_path') or _find_speedtest(
                        cfg.get('speedtest_path', ''))
                    out['data_file'] = DATA_FILE
                    out['data_file_kb'] = round(os.path.getsize(DATA_FILE) / 1024.0, 1) \
                        if os.path.exists(DATA_FILE) else 0
                except Exception:
                    pass
                self._json(200, out)
                return

            with _lock:
                data = _load_data()

            if path == '/status':
                self._json(200, self._status_snapshot(data))
                return

            if path == '/data':
                self._json(200, data)
                return

            self._not_found()

        def do_POST(self):
            path = self.path.split('?')[0].rstrip('/')

            if not self._auth():
                self._unauth(); return

            if path == '/run':
                if _running_test:
                    self._json(409, {'error': 'test already running'})
                    return
                threading.Thread(target=_worker_speedtest, args=(cfg,),
                                 daemon=True).start()
                self._json(202, {'queued': True, 'message': 'speed test started'})
                return

            if path == '/dns':
                if _running_dns:
                    self._json(409, {'error': 'DNS check already running'})
                    return
                threading.Thread(target=_worker_dns, daemon=True).start()
                self._json(202, {'queued': True, 'message': 'DNS check started'})
                return

            self._not_found()

        def do_OPTIONS(self):
            # CORS preflight
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.end_headers()

    return Handler


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Speedtest Network Monitor Agent')
    parser.add_argument('--port',     type=int,   default=None)
    parser.add_argument('--interval', type=int,   default=None,
                        help='Test interval in minutes')
    parser.add_argument('--host',     type=str,   default=None,
                        help='Bind host (default 0.0.0.0)')
    parser.add_argument('--token',    type=str,   default=None,
                        help='Bearer token for API auth')
    parser.add_argument('--speedtest', type=str,  default=None,
                        help='Path to speedtest.exe')
    parser.add_argument('--no-auto-install', action='store_true',
                        help='Do not attempt to pip install psutil on first run')
    args = parser.parse_args()

    # Make sure psutil is available before we start reporting system detail.
    _PS_OK, _PS_WHY = _ensure_psutil(auto=not args.no_auto_install)
    globals()['_PSUTIL_STATE'] = _PS_WHY

    # Load config, then override with CLI args
    cfg = _load_config()
    if args.port     is not None: cfg['port']             = args.port
    if args.interval is not None: cfg['interval_minutes'] = args.interval
    if args.host     is not None: cfg['bind_host']        = args.host
    if args.token    is not None: cfg['token']            = args.token
    if args.speedtest is not None: cfg['speedtest_path']  = args.speedtest

    _save_config(cfg)

    port    = cfg.get('port',      DEFAULT_PORT)
    bind    = cfg.get('bind_host', DEFAULT_BIND)
    exe     = _find_speedtest(cfg.get('speedtest_path', ''))
    interval = cfg.get('interval_minutes', DEFAULT_INTERVAL)

    print('=' * 60)
    print(f'  Speedtest Agent  v{VERSION}')
    print('=' * 60)
    print(f'  Hostname : {socket.gethostname()}')
    print(f'  Local IP : {_local_ip()}')
    print(f'  Bind     : {bind}:{port}')
    print(f'  Interval : every {interval} min')
    print(f'  Speedtest: {exe}')
    print(f'  Data file: {DATA_FILE}')
    if cfg.get('token'):
        print(f'  Auth     : Bearer token enabled')
    else:
        print(f'  Auth     : none (open)')
    print('=' * 60)
    print(f'  API endpoints:')
    print(f'    GET  http://{_local_ip()}:{port}/info')
    print(f'    GET  http://{_local_ip()}:{port}/status')
    print(f'    GET  http://{_local_ip()}:{port}/data')
    print(f'    POST http://{_local_ip()}:{port}/run')
    print(f'    POST http://{_local_ip()}:{port}/dns')
    print(f'    GET  http://{_local_ip()}:{port}/health')
    print('=' * 60, flush=True)

    if not Path(exe).exists():
        print(f'\n  WARNING: speedtest.exe not found at: {exe}')
        print(f'  Copy speedtest.exe next to this script, or use --speedtest <path>\n',
              flush=True)

    # Start the background test scheduler
    threading.Thread(target=_schedule_loop, args=(cfg,), daemon=True).start()

    # Start the HTTP server
    server = ThreadingHTTPServer((bind, port), _make_handler(cfg))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down.', flush=True)
        server.shutdown()


if __name__ == '__main__':
    main()
