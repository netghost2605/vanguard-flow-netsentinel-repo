#!/usr/bin/env python3
"""The /lidar page and its API: state, map, placement, learning, pairing, demo, switches, safety rules.
Run: python3 test_lidar_web.py"""
import os, sys, json, time, math, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import csiweb_harness as CH
H = CH.H; mod = CH.mod
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
port, mon, w, srv, state = CH.make(seed_week=False)
base = 'http://127.0.0.1:%d' % port
def get(p):
    return json.loads(urllib.request.urlopen(base + p, timeout=15).read())
def post(p, body, headers=None):
    h = {'Content-Type': 'application/json'}; h.update(headers or {})
    rq = urllib.request.Request(base + p, data=json.dumps(body).encode(), headers=h, method='POST')
    try:
        r = urllib.request.urlopen(rq, timeout=10); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

pg = urllib.request.urlopen(base + '/lidar').read().decode()
check('@@' not in pg and 'id="cMap"' in pg and 'Lidar Room Map' in pg and '--acc:' + H.mod.THEMES['Ocean']['download'] in pg and 'AI' in pg, 'page: theme tokens replaced, map canvas, AI widget')
check("h:'/lidar'" not in urllib.request.urlopen(base + '/').read().decode(), 'dashboard menu no longer links to /lidar (switched off)')
check('href="/lidar"' not in urllib.request.urlopen(base + '/wifi').read().decode(), '/wifi no longer links to /lidar (switched off)')

st = get('/api/lidar/state')
check(st['ok'] and st['nodes'] == [] and st['prefs']['lidar_on'] is False and st['prefs']['lidar_alert'] == 'away' and st['can_act'] and st['local'] and st['port'] == 4220, 'state: nothing yet, listening off, PC may act')
check(st['floors']['down']['w'] == 12 and set(st['floors']) == {'down', 'up'} and len(st['spots']) == 4 and st['names']['up'], 'state: floor sizes, taught places, floor names')
check(st['night']['on'] is not None, 'state: night alarm status included')
mp = get('/api/lidar/map?floor=up')
check(mp['ok'] and mp['floor'] == 'up' and mp['nodes'] == [] and mp['tracks'] == [], 'map: empty floor')

CL = [time.time()]
hub = w.lidar_hub()
hub.clock = lambda: CL[0]
s_, r = post('/api/lidar/act', {'action': 'demo', 'on': True})
check(s_ == 200 and r['ok'] and hub.demo_on and hub.running, 'demo: switched on from the PC (hub starts)')
for _ in range(260):
    CL[0] += 0.1
    hub.demo_step(CL[0]); hub.tick(CL[0])
st = get('/api/lidar/state')
check(2 <= len(st['nodes']) <= 5 and all(n['live'] and n['has_bg'] and n['demo'] for n in st['nodes']), 'demo: the pretend lidars live with their room learned')
check(1 <= st['people'] <= 3 and st['tracks'][0]['floor'] == 'down' and st['demo'], 'demo: people followed (%s)' % st['tracks'])
mp = get('/api/lidar/map?floor=down')
check(len(mp['nodes']) == len(st['nodes']) and all(len(n['bg']) > 60 and len(n['scan']) > 50 for n in mp['nodes']) and 1 <= len(mp['tracks']) <= 3, 'map: room outline and live scan for each lidar, people on the floor')
check(mp.get('coverage', 0) >= 0.9 and len(mp.get('rooms') or []) >= 4, 'map: coverage of the floor (%s) and the pretend walls are sent' % mp.get('coverage'))
check(all(-0.3 <= p[0] <= 12.3 and -0.3 <= p[1] <= 8.3 for n in mp['nodes'] for p in n['bg']), 'map: outline points lie inside the plan')
check(get('/api/lidar/map?floor=up')['nodes'] == [], 'map: the other floor stays empty')
check('lidar' in w.night.last_seen, 'night alarm is being fed by the lidars')
# placement
s_, r = post('/api/lidar/act', {'action': 'pose', 'lid': 'D1', 'x': 1.5, 'y': 2.25, 'rot': 30, 'cw': False, 'floor': 'up', 'name': 'Hall'})
n1 = [n for n in get('/api/lidar/state')['nodes'] if n['id'] == 'D1'][0]
check(s_ == 200 and n1['pose']['x'] == 1.5 and n1['pose']['y'] == 2.25 and n1['pose']['rot'] == 30 and n1['pose']['cw'] is False and n1['pose']['floor'] == 'up' and n1['name'] == 'Hall', 'pose: position, facing, direction, floor and name saved')
s_, r = post('/api/lidar/act', {'action': 'nudge', 'lid': 'D1', 'dx': 0.1, 'dy': -0.1, 'drot': 5})
n1 = [n for n in get('/api/lidar/state')['nodes'] if n['id'] == 'D1'][0]
check(abs(n1['pose']['x'] - 1.6) < 1e-9 and abs(n1['pose']['y'] - 2.15) < 1e-9 and abs(n1['pose']['rot'] - 35) < 1e-9, 'nudge: moves a little and turns')
s_, r = post('/api/lidar/act', {'action': 'pose', 'lid': 'D1', 'x': 'abc'}); check(s_ == 403 and 'numbers' in r['error'], 'pose: nonsense numbers refused')
s_, r = post('/api/lidar/act', {'action': 'pose', 'lid': 'D1', 'x': 900}); check(s_ == 403 and 'off the plan' in r['error'], 'pose: a position far off the plan refused')
s_, r = post('/api/lidar/act', {'action': 'pose', 'lid': 'nobody', 'x': 1}); check(s_ == 403 and 'Pick' in r['error'], 'pose: unknown lidar refused')
post('/api/lidar/act', {'action': 'pose', 'lid': 'D1', 'x': 0.3, 'y': 0.3, 'rot': 45, 'cw': True, 'floor': 'down'})
# learning and pairing
s_, r = post('/api/lidar/act', {'action': 'learn', 'lid': 'D2'})
check(s_ == 200 and hub.nodes['D2'].learning is not None, 'learn: starts for one lidar')
s_, r = post('/api/lidar/act', {'action': 'clear', 'lid': 'D2'})
check(s_ == 200 and hub.nodes['D2'].bg is None, 'clear: forgets the picture')
s_, r = post('/api/lidar/act', {'action': 'pair_begin', 'a': 'D1', 'b': 'D2'})
st = get('/api/lidar/state')
check(s_ == 200 and st['pair'] and st['pair']['a'] == 'D1', 'pair: begins and the state shows it')
s_, r = post('/api/lidar/act', {'action': 'pair_finish'}); check(s_ == 403 and 'matching' in r['error'], 'pair: finishing too early says why')
s_, r = post('/api/lidar/act', {'action': 'pair_begin', 'a': 'D1', 'b': 'D1'}); check(s_ == 403, 'pair: needs two different lidars')
post('/api/lidar/act', {'action': 'pair_cancel'})
# safety
s_, r = post('/api/lidar/act', {'action': 'bogus'}); check(s_ == 403 and 'Unknown' in r['error'], 'unknown action refused')
s_, r = post('/api/lidar/act', {'action': 'learn'}, {'Origin': 'http://evil.example'}); check(s_ == 403 and 'another web page' in r['error'], 'change from another web page (Origin) refused')
ok, msg = hub.act({'action': 'pose', 'lid': 'D1', 'x': 2}, False); check(not ok and 'Allow switching off' in msg, 'remote device: placement refused by default')
w.prefs['web_control'] = True
ok, msg = hub.act({'action': 'pose', 'lid': 'D1', 'x': 2}, False); check(ok and abs(hub.nodes['D1'].pose['x'] - 2) < 1e-9, 'remote device with the tick: placement allowed')
w.prefs['web_control'] = False
post('/api/lidar/act', {'action': 'pose', 'lid': 'D1', 'x': 0.3})
# alert mode
s_, r = post('/api/lidar/act', {'action': 'alert', 'mode': 'always'}); check(s_ == 200 and w.prefs['lidar_alert'] == 'always' and get('/api/lidar/state')['prefs']['lidar_alert'] == 'always', 'alert mode: always')
s_, r = post('/api/lidar/act', {'action': 'alert', 'mode': 'loud'}); check(s_ == 403, 'alert mode: junk refused')
post('/api/lidar/act', {'action': 'alert', 'mode': 'away'})
# demo off
s_, r = post('/api/lidar/act', {'action': 'demo', 'on': False})
check(s_ == 200 and not hub.demo_on and not hub.nodes and not hub.running, 'demo: off removes the pretend lidars and stops listening')
# the listening switch
s_, r = post('/api/wifi/set', {'key': 'lidar_on', 'value': True})
check(s_ == 200 and r['ok'] and w.prefs['lidar_on'] is True and hub.running, 'switch: listen for lidars on')
ok, msg = w.web_set('lidar_on', False, False); check(not ok and w.prefs['lidar_on'] is True, 'switch: a remote device may not switch listening off by default')
ok, msg = w.web_set('lidar_on', True, False); check(ok, 'switch: a remote device may switch it on')
s_, r = post('/api/wifi/set', {'key': 'lidar_on', 'value': False})
check(s_ == 200 and w.prefs['lidar_on'] is False and not hub.running, 'switch: off from the PC stops listening')
try:
    get('/api/lidar/nonsense'); _bad = False
except urllib.error.HTTPError as _e:
    _bad = _e.code == 404
check(_bad, 'unknown endpoint refused (404)')
saved = mod._nm_wifi_load('wifi_prefs.json', {}, w.state_dir)
check(saved.get('lidar_alert') == 'away' and 'lidar_on' in saved, 'switches are saved with the other preferences')
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
