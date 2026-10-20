#!/usr/bin/env python3
"""T-Pot in a VM: login, pinned certificate, protected password, status, control.
Run: python3 test_tpot_remote.py"""
import importlib.util, os, sys, json, ssl, threading, tempfile, subprocess, base64, http.server, time
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ['NM_WIFI_TEST'] = '1'
os.environ['LOCALAPPDATA'] = TMP
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

def mkcert(tag):
    k, c = os.path.join(TMP, tag + '.key'), os.path.join(TMP, tag + '.crt')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', k, '-out', c, '-days', '2',
                    '-subj', '/CN=tpot-' + tag], check=True, capture_output=True)
    return k, c

GOOD = 'Basic ' + base64.b64encode(b'netsentinel:s3cret-pw').decode()
seen = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _do(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n) if n else b''
        seen.append((self.command, self.path, self.headers.get('Authorization')))
        if self.headers.get('Authorization') != GOOD:
            self.send_response(401); self.end_headers(); return
        if self.path.startswith('/es/_cluster/health'): out = {'status': 'yellow'}
        elif '_count' in self.path: out = {'count': 321}
        elif '_search' in self.path: out = {'hits': {'hits': [], 'total': {'value': 0}}, 'aggregations': {}}
        else: out = {}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    do_GET = _do; do_POST = _do

def serve(tag):
    k, c = mkcert(tag)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(c, k)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]

srv, port = serve('a')

# host rules
ok = mod._nm_tpot_host_ok
check(ok('192.168.1.146') and ok('10.0.0.5') and ok('172.20.1.1') and ok('tpot') and ok('tpot.local') and ok('127.0.0.1'), 'private addresses and local names allowed')
check(not ok('8.8.8.8') and not ok('example.com') and not ok('') and not ok('a b') and not ok('1.2.3.4.5'), 'public hosts and junk refused')

# protection round trip
t = mod._nm_secret_protect('pässword')
check(mod._nm_secret_unprotect(t) == 'pässword' and t.split(':')[0] in ('b64', 'dpapi'), 'password protect/unprotect round trip')

# bad input never reaches the network
r = mod._nm_tpot_remote_set('8.8.8.8', 'u', 'p')
check(not r['ok'] and 'own network' in r['error'], 'public host refused: %s' % r['error'])
r = mod._nm_tpot_remote_set('', 'u', 'p')
check(not r['ok'] and 'Enter the VM' in r['error'], 'blank address gets a clear message: %s' % r['error'])
r = mod._nm_tpot_remote_set('127.0.0.1:%d' % port, '', 'p')
check(not r['ok'] and 'user name' in r['error'], 'missing user refused')
check(mod._nm_tpot_remote_load() is None and not seen, 'nothing saved, nothing sent')

# wrong password: not saved
r = mod._nm_tpot_remote_set('127.0.0.1:%d' % port, 'netsentinel', 'wrong')
check(not r['ok'] and '401' in r['error'] and mod._nm_tpot_remote_load() is None, 'wrong login is refused and not saved: %s' % r['error'])

# good login (a pasted URL is accepted)
r = mod._nm_tpot_remote_set('https://127.0.0.1:%d/' % port, 'netsentinel', 's3cret-pw')
check(r['ok'], 'good login saved: %s' % r)
raw = open(os.path.join(TMP, 'NetworkMonitor', mod._NM_TPOT_REMOTE_FILE)).read()
check('s3cret-pw' not in raw, 'password is not in the file as plain text')
info = mod._nm_tpot_remote_info()
check(info == {'configured': True, 'host': '127.0.0.1', 'port': port, 'user': 'netsentinel', 'pinned': True}, 'page info: %s' % info)
check('s3cret' not in json.dumps(info) and 'fp' not in info, 'info never carries the password or the fingerprint')

# prefs and transport
pr = mod._nm_hp_prefs()
check(pr['remote'] and pr['es'] == 'https://127.0.0.1:%d/es' % port and pr['host'] == '127.0.0.1', 'prefs point at the portal: %s' % pr['es'])
st = mod._nm_tpot_status()
check(st['state'] == 'running' and st['events'] == 321 and st['remote'] and not st['docker'], 'remote status running with event count: %s' % {k: st[k] for k in ('state', 'events')})
check(all(a == GOOD for (_, _, a) in seen[-3:]), 'every request carried the login')
snap = mod._nm_tpot_snapshot(force=True)
check(snap['remote']['configured'] and 's3cret' not in json.dumps(snap) and snap['links'][0]['url'].startswith('https://127.0.0.1:%d/' % port), 'snapshot: links to the VM portal, no secrets')
hp = mod._NMTpotHoneypot(es_url=pr['es'], cursor_load=lambda: None, cursor_save=lambda t: None)
check(hp.start() == 1, 'the feed starts against the VM'); hp.stop()

# control
c = mod._nm_tpot_control({'action': 'start'}, local=True)
check(not c['ok'] and 'VM' in c['error'], 'start/stop refused in VM mode: %s' % c['error'])
c = mod._nm_tpot_control({'action': 'remote_clear'}, local=False)
check(not c['ok'], 'changing the connection is refused from another device')
c = mod._nm_tpot_control({'action': 'remote_set', 'host': '127.0.0.1:%d' % port, 'user': 'netsentinel', 'password': 'x', '_probe': 'evil'}, local=True)
check(not c['ok'], 'a request cannot inject its own probe')

# a changed certificate is refused (pin)
srv.shutdown(); srv.server_close()
srv2, port2 = serve('b')
rec = json.load(open(os.path.join(TMP, 'NetworkMonitor', mod._NM_TPOT_REMOTE_FILE)))
rec['port'] = port2
json.dump(rec, open(os.path.join(TMP, 'NetworkMonitor', mod._NM_TPOT_REMOTE_FILE), 'w'))
try:
    mod._nm_tpot_http('https://127.0.0.1:%d/es/_cluster/health' % port2)
    check(False, 'different certificate must be refused')
except Exception as ex:
    check('certificate changed' in str(ex), 'different certificate refused: %s' % str(ex)[:60])
before = len(seen)
st = mod._nm_tpot_status()
check(st['state'] == 'unreachable' and 'certificate' in st['error'] and len(seen) == before, 'status says unreachable and the login was not sent to the new certificate')

check(mod._NMTpotHoneypot(es_url='https://127.0.0.1:1/es').summary().get('remote') is True and not mod._NMTpotHoneypot().summary().get('remote'), 'summary tells the classic page whether T-Pot is in a VM')

# switching back
c = mod._nm_tpot_control({'action': 'remote_clear'}, local=True)
check(c['ok'] and mod._nm_tpot_remote_load() is None and mod._nm_hp_prefs()['es'] == mod._NM_TPOT_ES and not mod._nm_hp_prefs()['remote'], 'Use Docker again clears the VM connection')

# page
class _S: pass
html = mod._ThreeDServer._build_tpot_html(type('X', (), {'_monitor': None, '_nm_ai_widget_html': lambda self: ''})())
check('connCard' in html and 'remote_set' in html and 'type="password"' in html and 'cPass' in html, 'page has the connection card')
check('s3cret' not in html, 'page has no secrets')
print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
sys.exit(1 if fails else 0)
