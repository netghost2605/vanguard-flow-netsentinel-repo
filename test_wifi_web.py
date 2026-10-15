#!/usr/bin/env python3
"""The browser/phone /wifi page: data shape, the switches and their safety rule, same-origin check, JS walker == app walker.
Run: python3.12 test_wifi_web.py"""
import os, sys, json, time, subprocess, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import wifi_web_harness as H
import numpy as np
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
port, mon, w, srv = H.make()
def mod_acc_ok(pg):
    return ('--acc:' + H.mod.THEMES['Ocean']['download'] + ';') in pg
base = 'http://127.0.0.1:%d' % port
def get(p):
    return json.loads(urllib.request.urlopen(base + p, timeout=10).read())
def post(p, body, headers=None):
    h = {'Content-Type': 'application/json'}; h.update(headers or {})
    rq = urllib.request.Request(base + p, data=json.dumps(body).encode(), headers=h, method='POST')
    try:
        r = urllib.request.urlopen(rq, timeout=10); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
d = get('/api/wifi/web')
check(d['ok'] and d['chip'].startswith('BOARDS') and d['csi']['live'] and d['local'] and d['can_disarm'], 'web view: chip, boards live, local')
check(len(d['csi_hist']) > 100 and len(d['link_hist']) > 100 and d['health']['grade'] == 'B', 'web view: histories and health present')
check(all(len(f) == 4 for f in d['health']['factors']), 'web view: factors are (name, pts, max, note)')
a = get('/api/wifi/activity')
check(a['ok'] and len(a['grid']) == 7 and len(a['last24']) == 24 and a['events'], 'activity: grid, 24 h strip, events from the database')
m = get('/api/wifi/map')
check(m['ok'] and m['field'] and len(m['samples']) == 24 and m['router'], 'map: samples, smoothed field, router')
pg = urllib.request.urlopen(base + '/wifi').read().decode()
check('@@' not in pg and '<canvas id="cMan"' in pg and 'AI' in pg, 'page: theme tokens replaced, walker canvas, AI widget')
check(mod_acc_ok(pg), 'page: the accent comes from the app theme')
th0 = get('/api/wifi/web')['theme']
mon.config['theme'] = 'Crimson'
th1 = get('/api/wifi/web')['theme']
pg2 = urllib.request.urlopen(base + '/wifi').read().decode()
check(th0 and th1 and th0 != th1 and H.mod.THEMES['Crimson']['bg'] in pg2 and H.mod.THEMES['Crimson']['download'] in pg2,
      'theme change: the data says so (the page reloads) and the page is served in the new colours')
mon.config['theme'] = 'Ocean'
check("'/wifi'" in urllib.request.urlopen(base + '/').read().decode() or '/wifi' in urllib.request.urlopen(base + '/').read().decode(), 'dashboard menu links to /wifi')
# switches
s, r = post('/api/wifi/set', {'key': 'away', 'value': True})
check(s == 200 and r['ok'] and w.prefs['away'] is True, 'set: arm Away from the PC')
s, r = post('/api/wifi/set', {'key': 'away', 'value': False})
check(s == 200 and w.prefs['away'] is False, 'set: the PC itself may switch off')
s, r = post('/api/wifi/set', {'key': 'bogus', 'value': True})
check(s == 403 and 'Unknown' in r['error'], 'set: unknown key refused')
s, r = post('/api/wifi/set', {'key': 'away', 'value': True}, {'Origin': 'http://evil.example'})
check(s == 403 and w.prefs['away'] is False, 'set: another web page (Origin) refused')
s, r = post('/api/wifi/set', {'key': 'away', 'value': True}, {'Origin': base})
check(s == 200 and w.prefs['away'] is True, 'set: same-origin accepted')
w.set_pref('away', False)
# non-local rules (unit level; the test client is on loopback)
ok, msg = w.web_set('away', True, False); check(ok and w.prefs['away'] is True, 'remote: may arm')
ok, msg = w.web_set('away', False, False); check(not ok and w.prefs['away'] is True, 'remote: may NOT disarm by default')
ok, msg = w.web_set('web_control', True, False); check(not ok and not w.prefs['web_control'], 'remote: may not grant itself control')
ok, msg = w.web_set('web_control', True, True); check(ok and w.prefs['web_control'], 'PC: may allow remote disarm')
ok, msg = w.web_set('away', False, False); check(ok and w.prefs['away'] is False, 'remote: may disarm once the PC allowed it')
w.prefs['csi_port'] = ''; ok, msg = w.web_set('csi_bg', True, False); check(not ok and 'receiver' in msg, 'remote: Keep watching needs a chosen receiver')
# walker parity: JS cloud() == Python _nm_walker_cloud
html = open(os.path.join(HERE, '..', 'web', 'wifi.html'), encoding='utf-8').read()
js = html[html.index('function cloud('):html.index('var RAMP=')]
open('/tmp/_cl.js', 'w').write(js + "\nconsole.log(JSON.stringify([0,1.3,2.6,4.1].map(function(p){return cloud(p,84,128);})));")
out = json.loads(subprocess.check_output(['node', '/tmp/_cl.js']))
src = H.mod
okp = True
for p, jpts in zip([0, 1.3, 2.6, 4.1], out):
    pp = src._nm_walker_cloud(p, 84, 128)
    pp = [(float(q[0]), float(q[1])) for q in (pp if not isinstance(pp, tuple) else pp[0])]
    if len(pp) != len(jpts): okp = False; print('   count', p, len(pp), len(jpts)); continue
    dmax = max(max(abs(a[0] - b[0]), abs(a[1] - b[1])) for a, b in zip(pp, jpts))
    if dmax > 0.05: okp = False; print('   dmax', p, dmax)
check(okp, 'walker: the page draws the same body as the app (same points, 4 phases)')
print('\nRESULT:', 'PASS' if not fails else 'FAIL %d' % len(fails))
os._exit(1 if fails else 0)
