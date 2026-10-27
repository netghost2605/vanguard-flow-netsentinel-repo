#!/usr/bin/env python3
"""Smooth CSI graphs: a data update swaps the data on the saved empty graphs (no full redraw) and gives the SAME
picture as a full redraw; the frame loop slides both time graphs left with the clock; the walking man follows the
clock and draws each picture once. Run: xvfb-run -a python3.12 test_csi_smooth.py  (SMOOTH_SHOTS=<dir> saves pictures)"""
import importlib.util, os, sys, time, tempfile, threading
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod._NM_BOARDS_OFF = False        # these tests exercise the switched-off ESP32 / Floor / Lidar code
import numpy as np, tkinter as tk
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)
SHOT = os.environ.get('SMOOTH_SHOTS')
root = tk.Tk(); root.withdraw()
sd = tempfile.mkdtemp()
clock = [50000.0]
fr = tk.Toplevel(root); fr.geometry('1400x900+0+0')
ctl = mod._nm_csi_build_tab(fr, mod._NM_WIFI_DASH, fr, sd, clock=lambda: clock[0])
fr.update()
S = ctl['S']; an = S['an']; cv = ctl['cv']; sim = mod._NMCsiSim(seed=7, bpm=15.0)
class FakeSrc:
    lock = threading.Lock(); bad = 0; error = ''; log = []; raw = []
    def hint(self): return ''
    def stop(self): pass
    def copy_text(self, s=20): return ''
S['src'] = FakeSrc()
def feed(state, seconds):
    sim.state = state
    for i in range(int(seconds * 50)):
        t = clock[0] + i / 50.0
        p = mod._nm_csi_parse_line(sim.frame(t)); an.add(t, p['amp'], p['rssi'])
    clock[0] += seconds
def settle():
    for _ in range(4):
        fr.update(); fr.update_idletasks()
feed('empty', 40); ctl['draw'](force=True); settle()
feed('walking', 12); ctl['draw'](force=True); settle()
check('MOTION' in ctl['chip_m'].cget('text'), f"walking data drives the chip ({ctl['chip_m'].cget('text')})")
full0, fast0 = S.get('full', 0), S.get('fast', 0)
check(S.get('bg') is not None and S.get('axes') is not None, 'after a full redraw the empty graphs are saved for blitting')
feed('walking', 0.5); ctl['draw'](force=True); settle()
check(S.get('full', 0) == full0 and S.get('fast', 0) == fast0 + 1, f"a data update is a fast swap, not a full redraw (full {S.get('full')}, fast {S.get('fast')})")
fast_px = np.asarray(cv.buffer_rgba()).copy()
ctl['draw'](force=True, full=True); cv.draw(); settle()
full_px = np.asarray(cv.buffer_rgba()).copy()
check(S.get('full', 0) == full0 + 1, 'full=True forces a full redraw')
diff = np.abs(fast_px.astype(int) - full_px.astype(int)).max(axis=2)
bad = int((diff > 40).sum())
check(fast_px.shape == full_px.shape and bad < 0.0002 * diff.size,
      f'the fast swap draws the same picture as a full redraw ({bad} of {diff.size} pixels differ)')
if SHOT:
    from PIL import Image
    Image.fromarray(fast_px).save(os.path.join(SHOT, 'smooth_fast.png')); Image.fromarray(full_px).save(os.path.join(SHOT, 'smooth_full.png'))
# sliding with the clock
aw, am = S['axes'][0], S['axes'][1]
e0 = S['img'].get_extent()[1]
t0 = S['tf'].get_matrix()[0, 2]
clock[0] += 0.3; ctl['apply_shift'](); ok = ctl['blit'](S['axes'][:2])
e1 = S['img'].get_extent()[1]
t1 = S['tf'].get_matrix()[0, 2]
check(ok and abs((e0 - e1) - 0.3) < 1e-6 and abs((t0 - t1) - 0.3) < 1e-6,
      f'0.3 s later the heat map and the line have both slid 0.3 s left ({e0:.2f}->{e1:.2f}, {t0:.2f}->{t1:.2f})')
check(abs(t0 - 0.75) < 1e-6 and e0 > 0, f'right after new data the newest 0.75 s waits just off the right edge ({t0:.2f})')
lo_, hi_ = S['img'].get_extent()[:2]
check(lo_ <= -60.0 and hi_ >= 0.0, f'no gap at either edge while sliding ({lo_:.2f}..{hi_:.2f})')
clock[0] += 5.0; ctl['apply_shift']()
check(abs(S['tf'].get_matrix()[0, 2] + 0.5) < 1e-6, 'if data stops, the slide stops half a second past the edge (no runaway)')
# reviewing history does not slide
S['live'] = False; ctl['apply_shift'](); check(S['tf'].get_matrix()[0, 2] == 0.0, 'history view: no slide'); S['live'] = True
# the walking man: follows the clock, each picture drawn once per size
pw = ctl['pw']; pw.set_size(120, 176)
renders = []
orig = mod._nm_walker_cloud
def counting(*a, **k):
    renders.append(1); return orig(*a, **k)
mod._nm_walker_cloud = counting
cyc = pw.CYCLE_S
for i in range(200):
    pw.tick(1000.0 + i * cyc / 60.0)          # 60 updates per stride, for ~3.3 strides
first = len(renders)
check(first == pw.N_FRAMES, f'one stride draws each of its {pw.N_FRAMES} pictures exactly once ({first})')
check(pw.frames >= 3 * pw.N_FRAMES, f'later strides replay the saved pictures ({pw.frames} shown, {first} drawn)')
check(abs(pw.phase - (2 * np.pi * (int(((1000.0 + 199 * cyc / 60.0) / cyc) * pw.N_FRAMES) % pw.N_FRAMES) / pw.N_FRAMES)) < 1e-9,
      'the stride position comes from the clock, so a late frame does not slow him down')
pw.set_size(100, 150); pw.tick(5000.0)
check(len(renders) == first + 1 and len(pw._cache) == 1, 'a new size starts a fresh set of pictures')
mod._nm_walker_cloud = orig
# a resize redraws fully, then data updates are fast again
fr.geometry('1100x800'); settle(); feed('walking', 0.5); ctl['draw'](force=True); settle()
f2 = S.get('full', 0); feed('walking', 0.5); ctl['draw'](force=True); settle()
check(S.get('full', 0) == f2, 'after a resize the next update rebuilds once, then updates are fast again')
ctl['close'](); fr.destroy(); root.update()
print('RESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
