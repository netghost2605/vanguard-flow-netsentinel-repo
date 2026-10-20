#!/usr/bin/env python3
"""The /csi page: data shapes, history, floors, calibration safety rule, switches, same-origin check.
Run: python3 test_csi_web.py"""
import os, sys, json, time, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import csiweb_harness as CH
H = CH.H; mod = CH.mod
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
port, mon, w, srv, state = CH.make()
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

pg = urllib.request.urlopen(base + '/csi').read().decode()
check('@@' not in pg and 'id="cHeat"' in pg and 'AI' in pg and '--acc:' + H.mod.THEMES['Ocean']['download'] in pg, 'page: theme tokens replaced, heat canvas, AI widget')
check('/csi' in urllib.request.urlopen(base + '/').read().decode(), 'dashboard menu links to /csi')
check('href="/csi"' in urllib.request.urlopen(base + '/wifi').read().decode(), '/wifi links to /csi')

f = get('/api/csi/feeds')
check(f['ok'] and [x['id'] for x in f['feeds']] == ['board', 'down', 'up'] and all(x['live'] for x in f['feeds']) and f['can_act'] and f['local'], 'feeds: board and both floors live, PC may act')
check(f['hist']['lo'] and f['hist']['hi'] and f['csi_bg'] and f['floor_bg'] is False, 'feeds: history bounds and the two switches')
b = get('/api/csi/live?feed=board')
check(b['ok'] and b['live'] and b['owner'] == 'tab' and len(b['heat']) == 8 and len(b['heat'][0]) == 122, 'live board: 8 x 122 heat map, owned by the tab')
check(all(-1 <= v <= 100 for r in b['heat'] for v in r), 'live board: heat values are 0..100 or -1')
check(b['shape'] and len(b['shape']['now']) == 64 and b['shape']['ref'] and len(b['turb']) > 20 and b['thr'] is not None, 'live board: signal shape with reference, movement line, threshold')
check(b['chip'].startswith(('STILL', 'MOTION')) and b['room']['text'].startswith('ROOM') and b['cal']['when'], 'live board: chip, room, calibration time')
check(b['breath'].get('freqs') and len(b['breath']['freqs']) == len(b['breath']['power']), 'live board: breathing spectrum')
for fl in ('down', 'up'):
    d = get('/api/csi/live?feed=' + fl)
    check(d['ok'] and d['live'] and d['owner'] == 'window' and d['label'].endswith('link') and len(d['heat']) == 8, 'live %s link: live, read by the Floor window' % fl)
check(get('/api/csi/live?feed=bogus')['feed'] == 'board', 'live: an unknown feed falls back to the board')
fv = get('/api/csi/floor')
check(fv['ok'] and fv['active'] and fv['floors']['down']['w'] == 12 and fv['layout']['up']['tx'] == [1.5, 1.5] and len(fv['spots']) == 4, 'floors: sizes, Tx/Rx layout, taught places')
check(fv['chip'] == 'QUIET' or 'UPSTAIRS' in fv['chip'] or 'BOTH' in fv['chip'], 'floors: verdict chip (%s)' % fv['chip'])
check(len(fv['battery']) == 2 and 'Step 1' in fv['status'], 'floors: battery lines and the calibration step')
# board history
ov = get('/api/csi/hist/overview?range=3600&n=100')
check(ov['ok'] and not ov['empty'] and len(ov['real']) == 100 and ov['hi'] > ov['lo'], 'board history: overview over an hour')
ov2 = get('/api/csi/hist/overview?range=0')
check(ov2['ok'] and ov2['t1'] - ov2['t0'] > 9000, 'board history: "everything" spans the recording')
nx = get('/api/csi/hist/nav?t=%f&dir=1' % ov2['lo'])
check(nx['ok'] and nx['t'] is not None, 'board history: next movement from the start')
at = get('/api/csi/hist/at?t=%f' % (nx['t'] + 20))
check(at['ok'] and at['past'] and at['chip'].startswith('PAST') and len(at['heat']) == 8 and at['stats'], 'board history: a past moment looks like a live one')
gap = get('/api/csi/hist/at?t=%f' % (time.time() - 86400 * 3))
check(gap['ok'] and gap['empty'] and 'NOTHING' in gap['chip'], 'board history: a time with nothing recorded says so')
# floor history
fh = get('/api/csi/fhist?floor=up&n=100')
check(fh['ok'] and len(fh['cov']) == 100 and sum(1 for x in fh['mv'] if x > 0) > 10 and fh['span'][1] - fh['span'][0] > 6 * 86400, 'weekly history: a week of bins with movement')
check(fh['summary']['episodes'] > 50 and fh['summary']['place'] in ('Landing', 'Bedroom'), 'weekly history: summary names the busiest place')
pv = get('/api/csi/fhist/nav?floor=up&t=%f&dir=-1' % fh['t1'])
check(pv['ok'] and pv['t'] is not None, 'weekly history: previous movement from now')
a = get('/api/csi/fhist/at?floor=up&t=%f' % pv['t'])
check(a['ok'] and a['covered'] and a['moving'] and a['place'] in ('Landing', 'Bedroom'), 'weekly history: that moment reads as movement near a place (%s)' % a)
check(not get('/api/csi/fhist?floor=sideways')['ok'], 'weekly history: bad floor refused')
try:
    get('/api/csi/nonsense'); _bad = False
except urllib.error.HTTPError as _e:
    _bad = _e.code == 404
check(_bad, 'unknown endpoint refused (404)')
# calibration: needs the PC or web_control
s, r = post('/api/csi/act', {'action': 'cal_empty', 'feed': 'floor'})
check(s == 200 and r['ok'], 'calibrate floors from the PC')
s, r = post('/api/csi/act', {'action': 'cal_floor', 'feed': 'floor', 'floor': 'up'})
check(s == 403 and 'empty room first' in r['error'], 'walking step refused until the empty room is learned')
s, r = post('/api/csi/act', {'action': 'cal_clear', 'feed': 'floor'})
check(s == 200 and r['ok'], 'clear floor calibration')
s, r = post('/api/csi/act', {'action': 'bogus'}); check(s == 403 and 'Unknown' in r['error'], 'unknown action refused')
s, r = post('/api/csi/act', {'action': 'cal_empty', 'feed': 'board'}, {'Origin': 'http://evil.example'})
check(s == 403 and 'another web page' in r['error'], 'calibration from another web page (Origin) refused')
s, r = post('/api/csi/act', {'action': 'cal_empty', 'feed': 'board'}, {'Origin': base})
check(s == 200 and r['ok'] and 'starts in' in r['message'] and w.csi_cal_after.get('board'), 'board calibration: leave-the-room countdown starts')
cw = w.csi_web()
ok, msg = cw.act({'action': 'cal_empty', 'feed': 'board'}, False)
check(not ok and 'Allow switching off' in msg, 'remote device: calibration refused by default')
w.prefs['web_control'] = True
ok, msg = cw.act({'action': 'cal_clear', 'feed': 'board'}, False)
check(ok and w.csi_tab['an'].empty is None, 'remote device with the tick: calibration can be cleared')
w.prefs['web_control'] = False
# nothing feeding
w.csi_tab = None; w.floor_win = None
d = get('/api/csi/live?feed=board'); check(d['ok'] and d['live'] is False and d['chip'] == 'NOT CONNECTED' and d['why'], 'board off: says why (%s)' % d['why'][:40])
d = get('/api/csi/live?feed=up'); check(d['live'] is False and 'two-floor' in d['why'], 'floors off: says why')
d = get('/api/csi/floor'); check(d['ok'] and not d['active'] and d['chip'] == 'NOT RUNNING' and len(d['spots']) == 4, 'floors off: plan and places still shown')
# switches
s, r = post('/api/wifi/set', {'key': 'floor_bg', 'value': True})
check(s == 200 and r['ok'] and w.prefs['floor_bg'] is True and 'Floor window' in r['message'], 'switch: floor_bg on, with no saved receivers it says to connect once')
s, r = post('/api/wifi/set', {'key': 'floor_bg', 'value': False}); check(s == 200 and w.prefs['floor_bg'] is False, 'switch: floor_bg off from the PC')
ok, msg = w.web_set('floor_bg', True, False); check(ok, 'remote: may switch the floor recorder on')
w.prefs['floor_bg'] = True
ok, msg = w.web_set('floor_bg', False, False); check(not ok and w.prefs['floor_bg'] is True, 'remote: may NOT switch it off by default')
w.prefs['floor_bg'] = False
# watcher-owned board: recorded into the history by itself, breath only while the page is open
an = mod._NMCsiAnalyzer(); an.want_breath = False
fs = CH.FS(an); sim = mod._NMCsiSim(seed=5)
w._csi_an, w._csi_src = an, fs
w.prefs.update({'csi_port': 'COM5', 'csi_bg': True})
w._threads_on = True
t0 = time.time() - 1.0
for i in range(30):
    fs.feed(sim.frame(t0 + i * 0.03), t0 + i * 0.03)
lo0, hi0 = w.csi_hist_db().bounds()
w._csi_poll(t0 + 0.9)
lo1, hi1 = w.csi_hist_db().bounds()
check(hi1 > hi0 and w._csi_sess is not None, 'background board: a row is added to the history each second')
w.csi_web_touch(); check(an.want_breath, 'page open: breathing analysis on for the background board')
w._csi_web_t -= 60; w._csi_poll(t0 + 0.95); check(an.want_breath is False, 'page closed for a while: breathing analysis off again')
d = get('/api/csi/live?feed=board'); check(d['live'] and d['owner'] == 'background', 'live board: read by the background watcher when the tab is closed')
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
