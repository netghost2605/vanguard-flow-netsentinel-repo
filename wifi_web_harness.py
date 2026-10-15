"""Serve the real /wifi page with synthetic board + Wi-Fi data (for tests and previews)."""
import importlib.util, os, sys, time, math, random, tempfile, threading, socket
os.environ['NM_WIFI_TEST'] = '1'
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class FakeMon:
    _db = None
    data = {"timestamps": [], "download": [], "upload": [], "ping": []}
    @property
    def colors(self):
        return mod.THEMES.get(self.config.get('theme', 'Ocean'), mod.THEMES['Ocean'])

    def __init__(self, port):
        self.config = {"web_bind": "127.0.0.1", "web_port": port, "theme": "Ocean", "custom": None,
                       "advertised_down": 0, "advertised_up": 0}

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def make(port=None, moving=True, state_dir=None, with_db=True):
    port = port or free_port()
    mon = FakeMon(port)
    state_dir = state_dir or tempfile.mkdtemp()
    if with_db:
        from datetime import datetime, timedelta
        mon._db = mod.SpeedDB(os.path.join(state_dir, 'h.db'))
        mod._nm_wifi_db_init(mon._db)
        n0 = datetime.now().replace(second=0, microsecond=0)
        r0 = random.Random(5)
        for dday in range(14):
            for hr in (7, 8, 12, 18, 19, 20, 21):
                for mi in range(60):
                    t0 = (n0 - timedelta(days=dday)).replace(hour=hr, minute=mi)
                    if t0 > n0: continue
                    mod._nm_wifi_db_put_minute(mon._db, t0.strftime('%Y-%m-%dT%H:%M'), 1.0 if r0.random() < (0.5 if hr in (18, 19, 20) else 0.15) else 0.0, 2.0, -54.0, 60)
        for k in range(1, 9):
            t1 = n0 - timedelta(hours=k * 2)
            mod._nm_wifi_db_put_event(mon._db, t1.strftime('%Y-%m-%dT%H:%M:%S'), 'MOVEMENT' if k % 3 else 'NEW AP', 'Boards saw movement' if k % 3 else 'FreeWifi appeared') if hasattr(mod, '_nm_wifi_db_put_event') else None
        import json as _j
        _j.dump({'plan': {'w': 12, 'h': 8, 'images': {}, 'routers': {'0': [9.3, 5.1]}},
                 'samples': [{'x': x, 'y': y, 'z': 0, 'link': -45 - 3.2 * ((x - 9.3) ** 2 + (y - 5.1) ** 2) ** .5 + r0.gauss(0, 1.5), 'bssid': 'aa', 't': 0, 'aps': {}, 'bands': {}}
                             for x in range(1, 12, 2) for y in range(1, 8, 2)]},
                open(os.path.join(state_dir, 'wifi_survey.json'), 'w'))
    w = mod._nm_wifi_get_watcher(mon, create=True, state_dir=state_dir, use_api=False, threads=False,
                                 alert_fn=lambda *a: None, idle_fn=lambda: 5.0)
    w._started = True
    now = time.time(); rnd = random.Random(3)
    w.link = {'ssid': 'HomeNet', 'dbm': -52.0, 'pct': 82, 'channel': 36, 'band': '5 GHz', 'bssid': 'a4:2b:b0:aa:bb:cc'}
    w.link_t = now
    for i in range(300, 0, -1):
        w.link_hist.append((now - i, -52 + 2.2 * math.sin(i / 9.0) + rnd.gauss(0, .6)))
        sd = 0.6 + (3.4 if 90 < i < 140 else 0) + abs(rnd.gauss(0, .15))
        w.motion.stds.append((now - i, sd))
        lv = 0.04 + (0.25 if 90 < i < 140 or (moving and i < 25) else 0) + abs(rnd.gauss(0, .01))
        w.csi_hist.append((now - i, lv, 0.12, lv > 0.12, -48 + rnd.gauss(0, 1)))
    w.motion.thr = 1.8; w.motion.base = 0.7
    w.moves = [(now - 140, now - 90)]
    w.csi_moves = [(now - 140, now - 90)]
    if moving:
        w.csi_move_start = now - 20
    w.csi_state.update({'t': now, 'moving': moving, 'rate': 48.0, 'owner': 'bg'})
    w._csi_last_data = now
    w.aps = [{'ssid': 'HomeNet', 'bssid': 'a4:2b:b0:aa:bb:cc', 'dbm': -52, 'band': '5 GHz', 'channel': 36, 'maker': 'Netgear', 'auth': 'WPA2'},
             {'ssid': 'HomeNet', 'bssid': 'a4:2b:b0:aa:bb:cd', 'dbm': -61, 'band': '2.4 GHz', 'channel': 6, 'maker': 'Netgear', 'auth': 'WPA2'},
             {'ssid': 'BT-9XQ2', 'bssid': '10:22:33:44:55:66', 'dbm': -74, 'band': '2.4 GHz', 'channel': 11, 'maker': 'BT', 'auth': 'WPA2'},
             {'ssid': 'FreeWifi', 'bssid': 'de:ad:be:ef:00:01', 'dbm': -69, 'band': '2.4 GHz', 'channel': 1, 'maker': '', 'auth': 'Open', '_new': True}]
    w.health = {'score': 86, 'grade': 'B', 'factors': [('Signal', 28, 30, 'strong'), ('Channels', 18, 25, 'shared'), ('Security', 40, 45, 'one open network')]}
    w.findings = [{'sev': 'warn', 'text': 'Open network "FreeWifi" appeared nearby.'}]
    w.advice = ['Move the downstairs board closer to the hall.']
    w.event('MOVEMENT', 'Boards saw movement', alert=False)
    w.event('NEW AP', 'FreeWifi (open) appeared')
    w.prefs.update({'csi_port': 'COM5', 'csi_bg': True})
    def keep():
        while True:
            time.sleep(1.0)
            n = time.time()
            w.csi_state['t'] = n; w._csi_last_data = n
            lv = 0.04 + (0.25 if moving else 0) + abs(rnd.gauss(0, .01))
            w.csi_hist.append((n, lv, 0.12, lv > 0.12, -48 + rnd.gauss(0, 1)))
            w.link_hist.append((n, -52 + rnd.gauss(0, 1)))
    threading.Thread(target=keep, daemon=True).start()
    srv = mod._ThreeDServer(mon)
    threading.Thread(target=srv.serve, daemon=True).start()
    time.sleep(2.0)
    return port, mon, w, srv

if __name__ == '__main__':
    port, mon, w, srv = make(int(sys.argv[1]) if len(sys.argv) > 1 else None)
    print('PORT', port, flush=True)
    time.sleep(3600)
