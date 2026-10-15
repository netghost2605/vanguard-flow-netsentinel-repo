#!/usr/bin/env python3
"""_NMFloorDetector: two CSI links, learn each floor's movement split by calibration, then attribute
live movement to a floor by comparing the links. Run: python3 test_floor_detect.py"""
import importlib.util, os, sys, tempfile
os.environ['HOME'] = tempfile.mkdtemp()
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
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

print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
