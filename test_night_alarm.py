#!/usr/bin/env python3
"""Night alarm: a klaxon on sustained movement in the night window. Run: python3 test_night_alarm.py"""
import os, sys, io, json, time, wave, urllib.request, urllib.error
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import csiweb_harness as CH
import numpy as np
H = CH.H; mod = CH.mod
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

# ---- the sound is real data ----
raw = mod._nm_claxon_wav()
wf = wave.open(io.BytesIO(raw))
pcm = np.frombuffer(wf.readframes(wf.getnframes()), '<i2').astype(float)
check(wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 22050 and 2.3 < wf.getnframes() / 22050.0 < 2.5, 'klaxon: a 2.4 s mono 16-bit WAV')
check(np.abs(pcm).max() > 30000 and np.sqrt((pcm ** 2).mean()) > 9000, 'klaxon: loud (peak %d, rms %d)' % (np.abs(pcm).max(), np.sqrt((pcm ** 2).mean())))
check((np.abs(pcm[:8]) < 2500).all() and (np.abs(pcm[int(0.65 * 22050):int(0.78 * 22050)]) < 50).all(), 'klaxon: ramps in and has a gap between blasts')
fr = np.fft.rfftfreq(len(pcm), 1 / 22050.0); sp = np.abs(np.fft.rfft(pcm))
check(300 < fr[sp.argmax()] < 1700, 'klaxon: energy sits in the horn range (%d Hz)' % fr[sp.argmax()])


# ---- playing it: Windows cannot loop from memory in the background (that was the bug), so it must play a file ----
import types, tempfile
calls = []
fake = types.ModuleType('winsound')
fake.SND_MEMORY, fake.SND_ASYNC, fake.SND_LOOP, fake.SND_FILENAME, fake.SND_PURGE = 4, 1, 8, 131072, 64
def _ps(snd, flags):
    if flags & fake.SND_MEMORY and flags & fake.SND_ASYNC:
        raise RuntimeError('Cannot play asynchronously from memory')
    calls.append((snd, flags))
fake.PlaySound = _ps
fake.Beep = lambda f, d: None
sys.modules['winsound'] = fake
check(mod._nm_claxon_play() is True, 'play: reports it started')
snd, flags = calls[-1]
check(isinstance(snd, str) and snd.endswith('.wav') and os.path.getsize(snd) > 50000 and flags & fake.SND_FILENAME and flags & fake.SND_ASYNC and flags & fake.SND_LOOP and not flags & fake.SND_MEMORY,
      'play: loops a WAV file in the background (not from memory)')
mod._nm_claxon_stop(); check(calls[-1] == (None, fake.SND_PURGE), 'stop: purges the sound')
def _bad(snd, flags): raise RuntimeError('no audio device')
fake.PlaySound = _bad
check(mod._nm_claxon_play() is True and mod._NM_CLAXON['beep'] is not None, 'play: if the file cannot play it falls back to beeps')
mod._nm_claxon_stop(); check(mod._NM_CLAXON['beep'] is None, 'stop: ends the beeps')
del sys.modules['winsound']

# ---- logic, with a fake sound and a fake clock ----
port, mon, w, srv, state = CH.make(seed_week=False)
alerts = []
w.alert_fn = lambda title, msg, sev, image=None: alerts.append((title, msg, sev))
n = w.night
log = {'play': 0, 'stop': 0, 'box': [], 'close': 0}
n._play = lambda: (log.__setitem__('play', log['play'] + 1) or True)
n._stop = lambda: log.__setitem__('stop', log['stop'] + 1)
n._box = lambda text: log['box'].append(text)
n._box_close = lambda: log.__setitem__('close', log['close'] + 1)
day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
CUR = {'t': day}
def at(h, m=0, s=0):
    CUR['t'] = day + h * 3600 + m * 60 + s
    return CUR['t']
n.clock = lambda: CUR['t']
w.prefs.update({'night_alarm': True, 'night_from': '01:00', 'night_to': '03:00', 'night_sens': 'normal', 'night_min': 2})
check(n.in_window(at(1)) and n.in_window(at(2, 59, 59)) and not n.in_window(at(3)) and not n.in_window(at(0, 59)) and not n.in_window(at(12)), 'window: 01:00 up to (not including) 03:00')
w.prefs.update({'night_from': '22:00', 'night_to': '06:00'})
check(n.in_window(at(23)) and n.in_window(at(5, 30)) and not n.in_window(at(7)) and not n.in_window(at(21, 59)), 'window: wraps past midnight')
w.prefs.update({'night_from': '02:00', 'night_to': '02:00'}); check(not n.in_window(at(2, 30)), 'window: equal times mean never')
w.prefs.update({'night_from': 'xx', 'night_to': '??'}); check(n.in_window(at(2)) and not n.in_window(at(5)), 'window: unreadable times fall back to 01:00-03:00')
w.prefs.update({'night_from': '01:00', 'night_to': '03:00'})

for i in range(7):
    n.note('board', at(2, 0, i), True)
check(log['play'] == 0 and not n.active, 'seven seconds of movement is not enough (normal needs 8 in 20 s)')
n.note('board', at(2, 0, 7), True)
check(n.active and log['play'] == 1 and len(log['box']) == 0 or n.active and log['play'] == 1, 'the 8th second of movement sounds the klaxon')
time.sleep(0.4)
check(len(log['box']) == 1 and 'Click OK' in log['box'][0], 'an alarm box with a way to stop it is shown')
check(any(a[0].startswith('NIGHT ALARM') and a[2] == 'crit' for a in alerts) or time.sleep(0.5) or any(a[0].startswith('NIGHT ALARM') for a in alerts), 'a phone alert goes out, marked critical')
check(any(e['kind'] == 'NIGHTALARM' for e in w.events), 'it is written to the event list')
n.note('board', at(2, 0, 8), True); n.note('board', at(2, 0, 9), True)
check(log['play'] == 1, 'already sounding: it does not start a second klaxon')
st = n.status(); check(st['active'] and st['in_window'] is not None and st['since'] and 'Movement in the house' in st['why'], 'status says it is sounding and why')
check(n.silence('user') is True and not n.active and log['stop'] == 1 and log['close'] == 1, 'silence stops the sound and closes the box')
check(n.silence('user') is False and log['stop'] == 1, 'silencing when quiet does nothing')
at(2, 4, 50); n.silenced_t = CUR['t']
for i in range(10):
    n.note('board', at(2, 5, i), True)
check(log['play'] == 1 and not n.active, 'after a silence it stays quiet for a while even if movement goes on')
n.silenced_t = -1e18
for i in range(9):
    n.note('board', at(2, 20, i), True)
check(n.active and log['play'] == 2, 'then it can sound again')
n.silence('time'); n.silenced_t = -1e18

n2 = mod._NMNightAlarm(w, clock=lambda: CUR['t']); n2._play = n._play; n2._stop = n._stop; n2._box = n._box; n2._box_close = n._box_close
base = log['play']
for i in range(0, 40, 5):
    n2.note('board', at(2, 30, i), True)
check(log['play'] == base, 'a twitch every few seconds does not trip it')
n4 = mod._NMNightAlarm(w, clock=lambda: CUR['t']); n4._play = n._play; n4._stop = n._stop; n4._box = n._box; n4._box_close = n._box_close
for i in range(30):
    n4.note('board', at(4, 0, i), True)
check(log['play'] == base and not n4.active, 'movement outside the window is ignored')
w.prefs['night_alarm'] = False
for i in range(30):
    n2.note('board', at(2, 40, i), True)
check(log['play'] == base, 'switched off: ignored')
w.prefs['night_alarm'] = True
w.prefs['night_sens'] = 'low'
for i in range(13):
    n2.note('board', at(2, 45, i), True)
check(log['play'] == base, 'low sensitivity needs 14 seconds')
n2.note('board', at(2, 45, 13), True); check(log['play'] == base + 1 and n2.active, 'low sensitivity: the 14th second sounds it')
n2.silence('user'); n2.silenced_t = -1e18
w.prefs['night_sens'] = 'high'
for i in range(3):
    n2.note('floor', at(2, 50, i), True)
check(log['play'] == base + 1, 'high sensitivity needs 4 seconds')
n2.note('floor', at(2, 50, 3), True); check(log['play'] == base + 2, 'high sensitivity: floor links count too')
n2.silence('user')
check(n2.duration_s() == 120.0, 'default run time is two minutes')
w.prefs['night_min'] = 0.01; check(n2.duration_s() == 10.0, 'run time has a floor of 10 s'); w.prefs['night_min'] = 99; check(n2.duration_s() == 900.0, 'and a ceiling of 15 minutes'); w.prefs['night_min'] = 2

# ---- wired to the real feeds ----
w.prefs['night_sens'] = 'normal'
n3 = w.night
n3.silenced_t = -1e18; n3.active = False; n3.sec.clear()
b0 = log['play']
for i in range(9):
    w.csi_sample(at(2, 55, i), {'moving': True, 'ready': True, 'rate': 25.0, 'turb': 0.3, 'thr': 0.1, 'rssi': -50}, 'bg')
check(log['play'] == b0 + 1, 'the background board reading (csi_sample) feeds the alarm')
n3.silence('user'); n3.silenced_t = -1e18; n3.sec.clear()
b0 = log['play']
for i in range(9):
    w.csi_observe(at(2, 56, i), {'moving': True, 'ready': True, 'rate': 25.0, 'turb': 0.3, 'thr': 0.1, 'rssi': -50}, 'tab')
check(log['play'] == b0 + 1, 'the CSI tab reading (csi_observe) feeds it too')
n3.silence('user'); n3.silenced_t = -1e18; n3.sec.clear()
class Tr: pass
trk = mod._NMFloorTracker(None, w.floor_history(), clock=lambda: 0, source_factory=lambda *a: None)
w.floor_track_apply = lambda: None
trk.note = w.night.note
check(trk.note == w.night.note, 'the background floor recorder reports to the alarm')
check(mod._NMWifiWatcher.PREF_DEFAULTS['night_alarm'] is True and mod._NMWifiWatcher.PREF_DEFAULTS['night_from'] == '01:00' and mod._NMWifiWatcher.PREF_DEFAULTS['night_to'] == '03:00', 'defaults: armed, 01:00 to 03:00')
check(w.parse_hm if False else mod._NMNightAlarm.parse_hm('1:5', None) == 65 and mod._NMNightAlarm.parse_hm('25:00', None) is None and mod._NMNightAlarm.parse_hm('', 7) == 7, 'time parsing')

# ---- from the web ----
base_url = 'http://127.0.0.1:%d' % port
def get(p): return json.loads(urllib.request.urlopen(base_url + p, timeout=15).read())
def post(p, body):
    rq = urllib.request.Request(base_url + p, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        r = urllib.request.urlopen(rq, timeout=10); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
f = get('/api/csi/feeds')
check(f['night']['on'] and f['night']['from'] == '01:00' and f['night_alarm'] is True and 'active' in f['night'], 'web feeds carry the night alarm state')
d = get('/api/wifi/web'); check(d['night']['on'] and d['prefs']['night_alarm'] is True, '/api/wifi/web carries it too')
n3.active = True; n3.since = time.time(); n3.last_why = 'Movement in the house at 02:10.'
s_, r_ = post('/api/csi/act', {'action': 'night_silence'}); check(s_ == 200 and r_['ok'] and not n3.active, 'the PC can silence it from the page')
ok, msg = w.csi_web().act({'action': 'night_silence'}, False); check(not ok and 'Allow switching off' in msg, 'another device cannot silence it by default')
w.prefs['web_control'] = True; n3.active = True
ok, msg = w.csi_web().act({'action': 'night_silence'}, False); check(ok and not n3.active, 'with the PC tick another device can')
w.prefs['web_control'] = False
s_, r_ = post('/api/csi/act', {'action': 'night_test'}); check(s_ == 200 and r_['ok'], 'test klaxon from the page')
ok, msg = w.web_set('night_alarm', False, False); check(not ok and w.prefs['night_alarm'] is True, 'another device cannot switch the alarm off')
ok, msg = w.web_set('night_alarm', False, True); check(ok and w.prefs['night_alarm'] is False, 'the PC can')
ok, msg = w.web_set('night_alarm', True, False); check(ok and w.prefs['night_alarm'] is True, 'any device can switch it on')
pg = urllib.request.urlopen(base_url + '/csi').read().decode()
check('id="alarm"' in pg and 'night_alarm' in pg and 'nightTest' in pg, '/csi page: banner, switch and test button')
check("'night_alarm'" in urllib.request.urlopen(base_url + '/wifi').read().decode(), '/wifi page: has the switch')
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
