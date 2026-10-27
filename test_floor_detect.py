#!/usr/bin/env python3
"""_NMFloorDetector: two CSI links, learn each floor's movement split by calibration, then attribute
live movement to a floor by comparing the links. Run: python3 test_floor_detect.py"""
import importlib.util, json, os, sys, tempfile
os.environ['HOME'] = tempfile.mkdtemp()
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod._NM_BOARDS_OFF = False        # these tests exercise the switched-off ESP32 / Floor / Lidar code
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)

# a controllable stand-in for _NMCsiAnalyzer: we drive snapshot() by hand, no real CSI needed
class FakeAn:
    def __init__(self): self.empty = None; self._cal = None
        # set from the test:
    cur = None
    def snapshot(self, t): return dict(self.cur or {'score': 0.0, 'moving': False})
    def start_calibration(self, t, dur): self._cal = {'t0': t, 'dur': dur}
    def cal_progress(self, t):
        if not self._cal: return None
        return min(1.0, (t - self._cal['t0']) / self._cal['dur'])
    def clear_calibration(self): self.empty = None; self._cal = None

CLK = {'t': 1000.0}
def clock(): return CLK['t']
def adv(dt): CLK['t'] += dt

det = mod._NMFloorDetector(clock=clock)
up, down = FakeAn(), FakeAn()
det.an['up'], det.an['down'] = up, down

def setlink(a, score, moving): a.cur = {'score': float(score), 'moving': bool(moving), 'rate': 100, 'rssi': -50, 'frames': 9}

# ── empty-baseline phase tracks both analyzers ──────────────────────────────
det.start_empty(dur=10.0)
check(0.0 <= det.empty_progress() < 0.2 and not det.empty_done(), 'empty calibration starts at ~0 and is not done')
adv(10.0); up.empty = {'mean': 1}; down.empty = {'mean': 1}
check(det.empty_done() and det.empty_progress() == 1.0, 'empty calibration finishes when both links have a baseline')

# ── uncalibrated fallback: raw dominance still attributes a floor ───────────
setlink(up, 20, True); setlink(down, 3, False)
v = det.tick()
check(v['floor'] == 'up' and 'uncalibrated' in v['label'], 'uncalibrated: only the upstairs link moving -> upstairs')
setlink(up, 2, False); setlink(down, 18, True)
v = det.tick()
check(v['floor'] == 'down', 'uncalibrated: only the downstairs link moving -> downstairs')

# ── calibrate the two floors (walk upstairs: up link dominates; downstairs: down link dominates) ──
det.start_floor('up', dur=5.0)
for _ in range(6):
    setlink(up, 18, True); setlink(down, 5, True); adv(1.0); det.tick()   # upstairs walk: split ~0.78
adv(1.0); det.tick()   # past dur -> finishes
det.start_floor('down', dur=5.0)
for _ in range(6):
    setlink(up, 4, True); setlink(down, 16, True); adv(1.0); det.tick()   # downstairs walk: split ~0.20
adv(1.0); det.tick()
check(det.calibrated(), 'both floors calibrated after two walks')
check(det.cal['up']['ratio'] > det.cal['down']['ratio'] + 0.3,
      'learned upstairs-share is clearly higher for the upstairs walk than the downstairs walk')

# ── live attribution using the learned splits ───────────────────────────────
det.alert_dwell = 0.0        # make alerts immediate for the test
hits = []
det.on_floor = lambda floor, detail: hits.append((floor, detail, CLK['t']))

setlink(up, 17, True); setlink(down, 6, True); adv(1.0)   # split ~0.74, closest to the upstairs centroid
v = det.tick()
check(v['floor'] == 'up' and v['moving'], 'live: an upstairs-like split is attributed to upstairs')

setlink(up, 5, True); setlink(down, 15, True); adv(1.0)   # split ~0.25, closest to downstairs
v = det.tick()
check(v['floor'] == 'down', 'live: a downstairs-like split is attributed to downstairs')

setlink(up, 12, True); setlink(down, 12, True); adv(1.0)  # split 0.5, equidistant -> both floors
v = det.tick()
check(v['floor'] == 'both', 'live: an even split with both links active -> both floors')

setlink(up, 0, False); setlink(down, 0, False); adv(1.0)
v = det.tick()
check(v['floor'] is None and not v['moving'] and v['label'] == 'quiet', 'live: no movement on either link -> quiet')

# ── alert callback: fires on a floor, debounced per floor by alert_gap ──────
det.alert_gap = 300.0
hits.clear()
setlink(up, 17, True); setlink(down, 6, True)
adv(1.0); det.tick()                       # first upstairs attribution -> alert
n1 = len(hits)
adv(1.0); det.tick()                       # still upstairs, within gap -> no new alert
check(n1 == 1 and len(hits) == 1 and hits[0][0] == 'up', 'a floor raises one alert, then stays quiet within the debounce gap')
adv(301.0); det.tick()                     # gap elapsed -> alerts again
check(len(hits) == 2, 'after the debounce gap the same floor can alert again')

# ── clearing calibration resets everything ──────────────────────────────────
det.clear_calibration()
check(not det.calibrated() and det.cal['up'] is None, 'clearing calibration forgets the learned splits')

# ── the detector is wired into the app (window opener + sidebar button + alert title) ──
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check('def _nm_open_floor(' in src, 'the floor-detection window opener exists')
check("'FLOORMOVE'" in src, 'the FLOORMOVE alert kind is referenced (title map + raise)')

# ── floor-plan view helpers (side-by-side floors) ───────────────────────────
try:
    import matplotlib; matplotlib.use('Agg')
    from matplotlib.figure import Figure
    Dp = {'bg': '#06101e', 'panel': '#0d2235', 'border': '#1d3b57', 'text': '#cfe3f5', 'text2': '#6b8299', 'accent': '#38b8f0'}
    pl = {'images': {}, 'routers': {'0': [3, 2]}, 'sizes': {'0': [12, 8]}, 'floors': {'0': 'Downstairs', '1': 'Upstairs'}}
    smp = [{'x': 1 + i, 'y': 1 + (i % 4), 'z': 0, 'link': -50 - i} for i in range(6)]
    ids = mod._nm_floor_ids(pl)
    check(ids == {'down': 0, 'up': 1}, 'floor ids map Downstairs=0 Upstairs=1')
    f = Figure(); ax = f.add_subplot(111)
    dm = mod._nm_floor_paint(ax, Dp, pl, smp, 0, 'Downstairs')
    check(dm['n'] == 6 and dm['W'] == 12, 'floor paint counts only that floor\'s samples')
    a_mv = mod._nm_floor_overlay(ax, dm['W'], dm['H'], [2, 2], [9, 5], True, 0.9)
    a_q = mod._nm_floor_overlay(ax, dm['W'], dm['H'], [2, 2], [9, 5], False, 0.0)
    check(len(a_mv) > len(a_q), 'a disturbed link draws a red zone on top of the quiet link line')
    a_nl = mod._nm_floor_overlay(ax, dm['W'], dm['H'], None, None, True, 0.5)
    check(len(a_nl) >= 1, 'with no board marks the whole floor is washed red')
    check(mod._nm_floor_overlay(ax, dm['W'], dm['H'], None, None, False, 0.0) == [], 'quiet + no marks draws nothing')
except Exception as _e:
    check(False, 'floor-plan helpers raised: %r' % (_e,))


# ---- battery: CSI_BATT lines from the Heltec boards, their text, and the low-battery alert ----
bsrc = mod._NMCsiSource(mod._NMCsiAnalyzer(), sim=None, clock=clock)
bsrc.feed_line('CSI_BATT,rx,02,4050,87', 1000.0)
bsrc.feed_line('CSI_BATT,tx,02,3462,2', 1000.0)
check(bsrc.battery['rx']['pct'] == 87 and bsrc.battery['rx']['mv'] == 4050, 'CSI_BATT rx parsed (%s)' % bsrc.battery.get('rx'))
check(bsrc.battery['tx']['pct'] == 2 and bsrc.battery['tx']['id'] == '02', 'CSI_BATT tx parsed')
bsrc.feed_line('CSI_BATT,rx,02,0,-1', 1001.0)
check(bsrc.battery['rx']['pct'] is None, 'pct -1 means no battery')
for bad in ('CSI_BATT,zz,02,4000,50', 'CSI_BATT,rx,02,abc,50', 'CSI_BATT,rx,02,4000,150', 'CSI_BATT,rx,02', 'CSI_BATT,rx,02,99999,50'):
    before = dict(bsrc.battery)
    bsrc.feed_line(bad, 1002.0)
    check(bsrc.battery == before, 'malformed battery line ignored: %s' % bad)
check(bsrc.lines >= 8 and not bsrc.bad and not bsrc.log, 'battery lines are not counted as bad CSI or shown as board messages')
check(mod._nm_batt_text({'pct': 87, 'mv': 4050, 't': 1000.0}, 1010.0) == '87% (4.05 V)', 'battery text')
check(mod._nm_batt_text({'pct': None, 'mv': 0, 't': 1000.0}, 1010.0) == 'no battery', 'no battery text')
check(mod._nm_batt_text({'pct': 50, 'mv': 3840, 't': 1000.0}, 1100.0) == 'no reading', 'stale reading -> no reading')
check(mod._nm_batt_text(None, 1000.0) == 'no reading', 'missing -> no reading')
check('receiver 87%' in mod._nm_batt_line('Upstairs', {'rx': {'pct': 87, 'mv': 4050, 't': 1000.0}}, 1005.0), 'battery line text')

class FakeW:
    def __init__(self): self.ev = []
    def event(self, kind, detail, alert=False, sev='warn', key=None, debounce=300.0):
        self.ev.append((kind, detail, key, debounce))
fw = FakeW(); memo = {}
mod._nm_batt_alert(fw, 'Upstairs', {'rx': {'pct': 55, 'mv': 3850, 't': 1000.0}}, memo, 1005.0)
check(not fw.ev, 'no alert at 55 %')
mod._nm_batt_alert(fw, 'Upstairs', {'rx': {'pct': 18, 'mv': 3720, 't': 1000.0}}, memo, 1005.0)
check(len(fw.ev) == 1 and fw.ev[0][0] == 'BATTERY' and 'low' in fw.ev[0][1] and '18%' in fw.ev[0][1], 'alert at 18 pct: %s' % (fw.ev,))
mod._nm_batt_alert(fw, 'Upstairs', {'rx': {'pct': 18, 'mv': 3720, 't': 1006.0}}, memo, 1010.0)
check(len(fw.ev) == 1, 'low alert is not repeated every tick')
mod._nm_batt_alert(fw, 'Upstairs', {'tx': {'pct': 4, 'mv': 3600, 't': 1010.0}}, memo, 1012.0)
check(len(fw.ev) == 2 and 'critically low' in fw.ev[1][1] and 'transmitter' in fw.ev[1][1], 'critical alert for the transmitter')
mod._nm_batt_alert(fw, 'Upstairs', {'rx': {'pct': 5, 'mv': 3600, 't': 100.0}}, {}, 1012.0)
check(len(fw.ev) == 2, 'a stale reading never alerts')
mod._nm_batt_alert(None, 'Upstairs', {'rx': {'pct': 5, 'mv': 3600, 't': 1012.0}}, {}, 1012.0)
mod._nm_batt_alert(fw, 'Upstairs', {'rx': {'pct': None, 'mv': 0, 't': 1012.0}}, {}, 1012.0)
check(len(fw.ev) == 2, 'no battery fitted never alerts')


# ---- spot locator: teach places, recognise them live (simulated rooms through the real analysers) ----
import numpy as _np
_rng = _np.random.RandomState(7)
NSC = 64
BASE = {f: 1.0 + 0.4 * _np.sin(_np.linspace(0, 5, NSC) + (0 if f == 'up' else 1.3)) for f in ('up', 'down')}
SPOTS = {}
for _nm in ('Kitchen', 'Hall', 'Lounge', 'Bedroom', 'Landing'):
    SPOTS[_nm] = {f: _rng.normal(0, 0.18, NSC) for f in ('up', 'down')}

class SimClock:
    def __init__(self): self.t = 5000.0
    def __call__(self): return self.t
sc = SimClock()
ldet = mod._NMFloorDetector(clock=sc)
loc = mod._NMSpotLocator(clock=sc)

def run_frames(seconds, spot=None, fps=60, walk=True):
    """Feed both analysers; when `spot` is given the body disturbs the link in that spot's way."""
    n = int(seconds * fps)
    for i in range(n):
        sc.t += 1.0 / fps
        for f in ('up', 'down'):
            amp = BASE[f].copy()
            if spot is not None:
                k = 1.0 + (0.35 * _np.sin(sc.t * 3.1) if walk else 0.0)
                amp = amp + SPOTS[spot][f] * k
            amp = amp + _rng.normal(0, 0.03, NSC)
            ldet.an[f].add(sc.t, amp * 100.0, -50)
        if i % 30 == 0:
            res = loc.feed(loc.features(ldet, sc.t), sc.t)
            if res is not None:
                run_frames.last = res
run_frames.last = None

check(loc.features(ldet, sc.t) is None, 'no fingerprint before the empty room is learned')
ldet.start_empty(dur=20.0)
run_frames(22)
check(ldet.empty_done(), 'empty room learned in the simulated rooms')
check(loc.features(ldet, sc.t) is not None, 'fingerprint available once the empty room is learned')

# a spot needs a name and a real floor
for bad in (('', 'up'), ('Kitchen', 'attic')):
    try:
        loc.start_learn(bad[0], bad[1], 1, 1); ok_ = False
    except ValueError:
        ok_ = True
    check(ok_, 'start_learn rejects %r' % (bad,))

# too little data -> refuses
loc.start_learn('Thin', 'down', 2.0, 3.0, dur=3.0)
run_frames(3.6)
check(run_frames.last and run_frames.last[0] is False and not loc.spots, 'a capture with too few readings is refused (%s)' % (run_frames.last,))

POS = {'Kitchen': ('down', 2.0, 8.0), 'Hall': ('down', 6.0, 3.0), 'Lounge': ('down', 9.0, 8.0),
       'Bedroom': ('up', 2.0, 8.0), 'Landing': ('up', 6.0, 3.0)}
for nm, (fl, x, y) in POS.items():
    run_frames(2.0)
    loc.start_learn(nm, fl, x, y, dur=15.0)
    run_frames(15.6, spot=nm)
    check(run_frames.last and run_frames.last[0], 'taught %s: %s' % (nm, run_frames.last[1][:70] if run_frames.last else None))
check(len(loc.spots) == 5 and all(len(s['samples']) >= loc.MIN_SAMPLES for s in loc.spots), 'five spots stored with their readings')
check('Self-check' in loc.self_check_text() and '100%' in loc.self_check_text() or 'Self-check' in loc.self_check_text(), 'self-check text produced: %s' % loc.self_check_text()[:90])
sck = loc.self_check()
check(sck is not None and sck[0] / sck[1] > 0.9, 'self-check on distinct simulated spots is high (%s/%s)' % (sck[0], sck[1]))

# live: stand in each spot (never trained on these exact frames) and ask
def live_answer(spot, floor_hint, secs=6.0):
    loc.quiet(); ans = None
    for _ in range(int(secs * 2)):
        run_frames(0.5, spot=spot)
        ans = loc.update(loc.features(ldet, sc.t), floor_hint)
    return ans
good = 0
for nm, (fl, x, y) in POS.items():
    a = live_answer(nm, fl)
    if a and a['name'] == nm and a['floor'] == fl and abs(a['x'] - x) < 0.01:
        good += 1
    else:
        print('   miss for', nm, a)
check(good == 5, 'live movement in each taught spot is recognised (%d/5)' % good)

# a floor hint limits the candidates: downstairs movement never answers with an upstairs spot
a = live_answer('Kitchen', 'down')
check(a and a['floor'] == 'down', 'floor hint keeps the answer on the floor that moved')
# "both floors" searches everything
a = live_answer('Bedroom', 'both')
check(a and a['name'] == 'Bedroom', 'both floors searches every spot')

# a stranger (a pattern nothing like any taught spot) is not forced onto a spot
SPOTS['Stranger'] = {f: _rng.normal(0, 0.9, NSC) for f in ('up', 'down')}
a = live_answer('Stranger', 'both', secs=6.0)
check(a is None, 'a body somewhere never taught is not forced onto a spot (%s)' % (a,))

# the answer lingers briefly after the movement stops, then clears
a = live_answer('Hall', 'down')
check(a and a['name'] == 'Hall', 'Hall recognised')
sc.t += 3.0
check(loc.shown(sc.t) is not None, 'last place still shown 3 s after movement stops')
sc.t += loc.HOLD_S
check(loc.shown(sc.t) is None, 'last place clears after the hold time')

# persistence round trip + bad data
js = json.dumps(loc.to_json())
loc2 = mod._NMSpotLocator(clock=sc); loc2.load(json.loads(js))
check([s['name'] for s in loc2.spots] == [s['name'] for s in loc.spots] and loc2.usable(), 'spots survive save and load')
f_ = loc.features(ldet, sc.t)
r1 = loc.classify(f_); r2 = loc2.classify(f_)
check((r1 or {}).get('name') == (r2 or {}).get('name'), 'a reloaded locator answers the same')
for bad in (None, {}, {'spots': 'x'}, {'spots': [{'name': '', 'floor': 'up', 'samples': [[1.0]]}]},
            {'spots': [{'name': 'A', 'floor': 'attic', 'samples': [[1.0]]}]},
            {'spots': [{'name': 'A', 'floor': 'up', 'samples': [[1.0], [1.0, 2.0]]}]}):
    l3 = mod._NMSpotLocator(clock=sc); l3.load(bad)
    check(l3.spots == [], 'bad spot data ignored: %r' % (str(bad)[:50],))

# retaking a spot replaces it; delete and clear work
run_frames(2.0)
loc.start_learn('kitchen', 'down', 3.0, 3.0, dur=15.0)
run_frames(15.6, spot='Kitchen')
check(len(loc.spots) == 5 and [s for s in loc.spots if s['name'].lower() == 'kitchen'][0]['x'] == 3.0, 'teaching the same name again replaces that spot')
check(loc.delete('Hall') and len(loc.spots) == 4 and not loc.delete('Nope'), 'delete removes one spot')
loc.clear()
check(loc.spots == [] and loc.classify(f_) is None, 'clear forgets every spot')
l4 = mod._NMSpotLocator(clock=sc)
check(l4.self_check() is None and 'at least two' in l4.self_check_text(), 'self-check asks for two spots when there are fewer')


# ---- the places drawn on a floor plan ----
import matplotlib
matplotlib.use('Agg')
import matplotlib.figure as _mfig
_fig = _mfig.Figure(); _ax = _fig.add_subplot(1, 1, 1); _ax.set_xlim(0, 12); _ax.set_ylim(10, 0)
_sp = [{'name': 'Kitchen', 'floor': 'down', 'x': 2.0, 'y': 8.0}, {'name': 'Hall', 'floor': 'down', 'x': 6.0, 'y': 3.0},
       {'name': 'Bedroom', 'floor': 'up', 'x': 3.0, 'y': 4.0}]
_a0 = mod._nm_floor_spots_layer(_ax, _sp, 'down', None)
check(len(_a0) == 4, 'two downstairs places draw a marker and a name each (%d artists)' % len(_a0))
_a1 = mod._nm_floor_spots_layer(_ax, _sp, 'down', {'name': 'Hall', 'floor': 'down'})
check(len(_a1) == 5, 'the place the movement is at also gets a soft ring (%d artists)' % len(_a1))
check(mod._nm_floor_spots_layer(_ax, _sp, 'up', {'name': 'Hall', 'floor': 'down'}) != [] and
      len(mod._nm_floor_spots_layer(_ax, _sp, 'up', {'name': 'Hall', 'floor': 'down'})) == 2, 'a place on the other floor is not highlighted')
check(_ax.get_xlim() == (0.0, 12.0) and _ax.get_ylim() == (10.0, 0.0), 'drawing places does not move the plan\'s axes')
check(mod._nm_floor_spots_layer(_ax, [], 'up', None) == [] and mod._nm_floor_spots_layer(_ax, None, 'up', None) == [], 'no places -> nothing drawn')

# ---- floor history: a week of per-minute summaries, per floor ----
HC = {'t': 1_700_000_000.0}
hist = mod._NMFloorHistory(clock=lambda: HC['t'])
def inf(up_ok=True, down_ok=True, mv=None, place=None, sc=20.0):
    return {'up': {'ok': up_ok, 'moving': mv == 'up', 'score': sc if mv == 'up' else 0.0, 'place': place if mv == 'up' else None},
            'down': {'ok': down_ok, 'moving': mv == 'down', 'score': sc if mv == 'down' else 0.0, 'place': place if mv == 'down' else None}}
# 10 minutes quiet, 3 minutes of upstairs movement near Landing, 10 more quiet, a gap, then downstairs movement
t0 = HC['t']
for i in range(20 * 60):                      # 10 min quiet at 0.5 s ticks
    HC['t'] += 0.5; hist.record(HC['t'], inf())
for i in range(6 * 60):                       # 3 min of movement
    HC['t'] += 0.5; hist.record(HC['t'], inf(mv='up', place='Landing', sc=25.0 + (i % 7)))
for i in range(20 * 60):
    HC['t'] += 0.5; hist.record(HC['t'], inf())
HC['t'] += 3600.0                             # the PC was off for an hour
for i in range(4 * 60):                       # 2 min downstairs, only the downstairs link is being watched
    HC['t'] += 0.5; hist.record(HC['t'], inf(up_ok=False, mv='down', place='Kitchen', sc=40.0))
a = hist.at('up', t0 + 11 * 60 + 90)
check(a['moving'] and a['place'] == 'Landing' and a['covered'] and 20 < a['sec'] <= 190 and a['peak'] >= 25,
      'mid-burst upstairs reads movement near Landing (%s)' % (a,))
q = hist.at('up', t0 + 2 * 60)
check(q['covered'] and not q['moving'] and q['place'] is None, 'a quiet minute is covered but not moving')
g = hist.at('up', t0 + 600 + 180 + 600 + 1800)
check(not g['covered'], 'the hour the PC was off is not covered (shown as not watching)')
gd = hist.at('down', t0 + 600 + 180 + 600 + 3600 + 60)
check(gd['moving'] and gd['place'] == 'Kitchen' and gd['covered'], 'downstairs burst after the gap is recorded with its place')
gu = hist.at('up', t0 + 600 + 180 + 600 + 3600 + 60)
check(not gu['covered'], 'a floor whose link had no data is not covered, even while the other floor was')
ep = hist.episodes('up', t0 - 10, HC['t'] + 10)
check(len(ep) == 1 and ep[0]['place'] == 'Landing' and 150 < ep[0]['sec'] < 200, 'one upstairs burst of ~3 minutes (%s)' % (ep,))
sm = hist.summary('down', t0 - 10, HC['t'] + 10)
check(sm['episodes'] == 1 and sm['place'] == 'Kitchen' and 100 < sm['sec'] < 130, 'downstairs summary (%s)' % (sm,))
nx = hist.neighbor('up', t0 + 60, 1, t0 - 10, HC['t'] + 10)
check(nx is not None and abs(nx - (t0 + 600)) < 120, 'next movement from the start jumps to the burst')
pv = hist.neighbor('up', HC['t'], -1, t0 - 10, HC['t'] + 10)
check(pv is not None and hist.at('up', pv)['moving'], 'previous movement from now lands on a burst')
check(hist.neighbor('up', pv, -1, t0 - 10, HC['t'] + 10) is None, 'nothing earlier than the first burst')
cv_, mv_, pk_ = hist.bins('up', t0, HC['t'], 48)
check(len(cv_) == 48 and sum(1 for x in mv_ if x > 0) >= 1 and sum(mv_) > 150 and max(pk_) >= 25,
      'binned series for the timeline carries the movement')
check(sum(1 for x in cv_ if x < 1) >= 1, 'the timeline bins over the gap have no coverage')
s0, s1 = hist.span(HC['t'])
check(abs(s0 - (t0 // 60) * 60) < 120 and s1 == HC['t'], 'span runs from the first recorded minute to now')
check(mod._NMFloorHistory(clock=lambda: HC['t']).span(HC['t'])[0] == HC['t'] - 3600.0, 'an empty history still spans an hour so the slider has a range')

# persistence: round trip, pruning past 7 days, hostile and broken files
js = json.dumps(hist.to_json())
h2 = mod._NMFloorHistory(clock=lambda: HC['t']); h2.load(json.loads(js), HC['t'])
check(h2.episodes('up', t0 - 10, HC['t']) == hist.episodes('up', t0 - 10, HC['t']) and h2.cov == hist.cov and not h2.dirty,
      'history survives save and load')
check(len(js) < 20000, 'a quarter hour of activity is a small file (%d bytes)' % len(js))
HC['t'] += 8 * 86400
h3 = mod._NMFloorHistory(clock=lambda: HC['t']); h3.load(json.loads(js), HC['t'])
check(not h3.cov['up'] and not h3.ev['up'] and not h3.ev['down'], 'data older than 7 days is dropped on load')
hist.record(HC['t'], inf(mv='up', place='Landing')); hist.prune(HC['t'])
check(all(m * 60 > HC['t'] - 7 * 86400 for m in hist.cov['up']) and len(hist.ev['up']) <= 1, 'pruning drops everything older than a week')
for bad in (None, [], {'cov': 5}, {'cov': {'up': [['a', 'b']]}}, {'ev': {'up': [[1, 'x', 2, 'p']]}}, {'ev': {'up': [[1]]}},
            {'cov': {'up': [[0, 10 ** 12]]}}):
    hb = mod._NMFloorHistory(clock=lambda: HC['t'])
    try:
        hb.load(bad, HC['t']); ok_ = len(hb.cov['up']) <= hb.keep_min + 1
    except Exception as ex:
        ok_ = False
    check(ok_, 'bad history data is ignored safely: %r' % (str(bad)[:40],))

# the on-disk helpers
_sd = tempfile.mkdtemp()
hh = mod._NMFloorHistory(clock=time.time if 'time' in dir() else None)
import time as _tm
hh.clock = _tm.time
hh.record(_tm.time(), inf(mv='up', place='Hall'))
check(mod._nm_floor_hist_save(hh, _sd, force=True) and os.path.exists(os.path.join(mod._nm_wifi_dir(_sd), 'floor_history.json')), 'history saved to floor_history.json')
check(not mod._nm_floor_hist_save(hh, _sd), 'an unchanged history is not rewritten')
hh.record(_tm.time() + 1, inf(mv='up', place='Hall'))
check(not mod._nm_floor_hist_save(hh, _sd), 'saves are rate limited (not more than once a minute)')
hr = mod._nm_floor_hist_open(_sd)
check(any(e[2] == 'Hall' for e in hr.ev['up'].values()), 'history reopens from disk with its place')

# what the recorder takes from a detector
idet = mod._NMFloorDetector(clock=clock)
idet.live = {'up': {'rate': 90.0}, 'down': {'rate': None}}
idet.verdict = {'floor': 'up', 'moving': True, 's_up': 31.0, 's_down': 4.0}
class _L:
    def shown(self): return {'name': 'Landing', 'floor': 'up'}
ii = mod._nm_floor_hist_info(idet, _L())
check(ii['up'] == {'ok': True, 'moving': True, 'score': 31.0, 'place': 'Landing'}, 'info: moving floor carries score and place (%s)' % (ii['up'],))
check(ii['down']['ok'] is False and not ii['down']['moving'], 'info: a floor whose link has no data is not ok')
idet.verdict = {'floor': 'both', 'moving': True, 's_up': 10.0, 's_down': 12.0}
idet.live['down'] = {'rate': 80.0}
ii = mod._nm_floor_hist_info(idet, _L())
check(ii['up']['moving'] and ii['down']['moving'] and ii['up']['place'] == 'Landing' and ii['down']['place'] is None,
      'info: "both floors" counts for both, the place only for its own floor')
idet.verdict = {'floor': None, 'moving': False, 's_up': 0.0, 's_down': 0.0}
ii = mod._nm_floor_hist_info(idet, None)
check(not ii['up']['moving'] and not ii['down']['moving'], 'info: quiet means neither floor moving')

# calibration survives a restart
_cd = tempfile.mkdtemp()
d1 = mod._NMFloorDetector(clock=clock)
d1.an['up'], d1.an['down'] = FakeAn(), FakeAn()
mod._nm_floor_cal_load(_cd, d1, {})
d1.cal = {'up': {'ratio': 0.8, 'mag': 30.0, 'n': 40}, 'down': {'ratio': 0.2, 'mag': 28.0, 'n': 35}}
memo_ = {}
check(mod._nm_floor_cal_save(_cd, d1, memo_) and not mod._nm_floor_cal_save(_cd, d1, memo_), 'floor split saved once, then only when it changes')
_emp = {'mean': _np.ones(64), 'mu': 1.0, 'sd': 0.1, 'dmu': 0.0, 'dsd': 0.1, 'n': 400, 'when': 1.0}
d1.an['up'].on_cal(_emp)
d2 = mod._NMFloorDetector(clock=clock)
d2.an['up'], d2.an['down'] = FakeAn(), FakeAn()
mod._nm_floor_cal_load(_cd, d2, {})
check(d2.calibrated() and abs(d2.cal['up']['ratio'] - 0.8) < 1e-9 and d2.cal['down']['n'] == 35, 'the learned floor split comes back after a restart')
check(d2.an['up'].empty is not None and d2.an['down'].empty is None, 'the empty-room profile comes back for the floor that had one')
d1.an['up'].on_cal(None)
d3 = mod._NMFloorDetector(clock=clock); d3.an['up'], d3.an['down'] = FakeAn(), FakeAn()
mod._nm_floor_cal_load(_cd, d3, {})
check(d3.an['up'].empty is None, 'clearing the calibration forgets the empty-room profile')

# receiver pick checks shared by the window and the background recorder
P = mod._nm_floor_picks_problem
check(P('', 'wifi 1.2.3.4') and P('COM3', 'COM3') and P('wifi:4210', 'COM4') is None and P('wifi 1.2.3.4', 'wifi 1.2.3.5') is None
      and P('wifi 1.2.3.4', 'wifi 1.2.3.4') and P('wifi:4210', 'wifi 1.2.3.5'), 'receiver picks are validated')

# the background recorder, end to end with fake boards
class FSrc:
    made = []
    def __init__(self, sel, an): self.sel, self.an, self.started, self.stopped = sel, an, False, False; FSrc.made.append(self)
    def start(self): self.started = True
    def stop(self): self.stopped = True
_pd = tempfile.mkdtemp()
mod._nm_wifi_save('floor_prefs.json', {'up': 'wifi 10.0.0.141', 'down': 'wifi 10.0.0.154'}, None)
tc = SimClock()
hist_t = mod._NMFloorHistory(clock=tc)
trk = mod._NMFloorTracker(_pd, hist_t, clock=tc, source_factory=lambda sel, an, clk: FSrc(sel, an))
trk.step()
check(len(FSrc.made) == 2 and all(s.started for s in FSrc.made) and trk.status == 'recording', 'tracker connects both boards from the saved picks (%s)' % trk.status)
check([s.sel for s in FSrc.made] == ['wifi 10.0.0.141', 'wifi 10.0.0.154'], 'upstairs and downstairs picks are not swapped')
for f_ in ('up', 'down'):
    trk.det.an[f_] = FakeAn()
setlink(trk.det.an['up'], 22, True); setlink(trk.det.an['down'], 3, False)
for _ in range(40):
    tc.t += 0.5; trk.step()
e_ = hist_t.at('up', tc.t - 5)
check(e_['moving'] and e_['covered'] and not hist_t.at('down', tc.t - 5)['moving'], 'tracker records upstairs movement with no window open')
trk.pause()
check(all(s.stopped for s in FSrc.made[:2]) and trk.status.startswith('paused'), 'pausing releases the boards (the Floor window takes over)')
n0 = sum(len(c) for c in hist_t.cov.values())
tc.t += 120.0; trk.step()
check(sum(len(c) for c in hist_t.cov.values()) == n0, 'a paused tracker records nothing')
trk.resume(); tc.t += 60.0; trk.step()
check(len(FSrc.made) == 4 and trk.status == 'recording', 'resuming reconnects both boards')
mod._nm_wifi_save('floor_prefs.json', {'up': 'wifi 10.0.0.141', 'down': 'wifi 10.0.0.141'}, None)
trk2 = mod._NMFloorTracker(_pd, mod._NMFloorHistory(clock=tc), clock=tc, source_factory=lambda sel, an, clk: FSrc(sel, an))
trk2.step()
check(trk2.src['up'] is None and 'choose the receivers' in trk2.status, 'tracker waits (does not guess) when the picks are not usable')
mod._nm_wifi_save('floor_prefs.json', {}, None)

# the watcher wires the tracker to the setting
FSrc.made.clear()
mod._nm_wifi_save('floor_prefs.json', {'up': 'wifi 10.0.0.141', 'down': 'wifi 10.0.0.154'}, None)
ww = mod._NMWifiWatcher(state_dir=_pd, use_api=False, threads=True)
ww.floor_source_factory = lambda sel, an, clk: FSrc(sel, an)
check(ww.floor_tracker is None, 'no background recorder until it is switched on')
ww.set_pref('floor_bg', True)
check(ww.floor_tracker is not None and ww.floor_tracker.running(), 'switching "floor_bg" on starts the recorder')
check(ww.floor_history() is ww.floor_tracker.hist, 'window and recorder share one history')
ww.set_pref('floor_bg', False)
check(ww.floor_tracker is None, 'switching it off stops the recorder')
ww2 = mod._NMWifiWatcher(state_dir=_pd, use_api=False, threads=False)
ww2.set_pref('floor_bg', True)
check(ww2.floor_tracker is None, 'a watcher without threads (tests) never starts the recorder')
check(mod._NMWifiWatcher.PREF_DEFAULTS.get('floor_bg') is False, 'background recording is off by default in the settings')

# ── a silent receiver must not be treated as movement on the other floor ──
sd = mod._NMFloorDetector(clock=clock)
sup, sdn = FakeAn(), FakeAn()
sd.an['up'], sd.an['down'] = sup, sdn
sup.empty = {'mean': 1}; sdn.empty = {'mean': 1}
sup.cur = {'score': 0.0, 'moving': True, 'rate': 0, 'rssi': -70, 'frames': 9}      # board off: stale "moving", no packets
sdn.cur = {'score': 90.0, 'moving': True, 'rate': 90, 'rssi': -50, 'frames': 9}
v = sd.tick()
check(v['floor'] is None and not v['moving'] and v['silent'] == ['up'], 'silent upstairs board -> no floor is claimed')
check('no data' in v['label'] and 'upstairs' in v['label'], 'the verdict says which receiver is silent')
fired = []
sd.on_floor = lambda f, d: fired.append(f)
for _ in range(5):
    adv(1.0); sd.tick()
check(not fired, 'no phone alert is raised while a receiver is silent')
sup.cur = {'score': 5.0, 'moving': False, 'rate': 95, 'rssi': -55, 'frames': 9}
v = sd.tick()
check(v['silent'] == [] and v['floor'] == 'down', 'both boards sending again -> normal verdict returns')
sdn.cur = {'score': 3.0, 'moving': False, 'rate': 0, 'rssi': -55, 'frames': 9}
sup.cur = {'score': 3.0, 'moving': False, 'rate': 0, 'rssi': -55, 'frames': 9}
v = sd.tick()
check(sorted(v['silent']) == ['down', 'up'] and 'upstairs and downstairs' in v['label'], 'both silent -> says both')
sd.start_floor('up', dur=5.0)
sup.cur = {'score': 20.0, 'moving': True, 'rate': 0, 'rssi': -55, 'frames': 9}
for _ in range(4):
    adv(1.0); sd.tick()
check(len(sd._learn['vals']) == 0, 'calibration does not record samples while a receiver is silent')

print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
