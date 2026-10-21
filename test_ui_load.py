#!/usr/bin/env python3
"""Interface-freeze watchdog and the window-state-aware redraw rates. Run: xvfb-run -a python3 test_ui_load.py"""
import importlib.util, os, sys, time, logging
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()

# ── _ui_state ──
class R:
    def __init__(s, state='normal', viewable=True, focus=object()): s._s, s._v, s._f = state, viewable, focus
    def state(s): return s._s
    def winfo_viewable(s): return s._v
    def focus_displayof(s): return s._f
class W: pass
w = W(); w._closed = False
st = mod.ModernWindow._ui_state
w.root = R(); check(st(w) == 'front', 'focused window: front')
w.root = R(focus=None); check(st(w) == 'back', 'visible without focus: back')
w.root = R(state='iconic'); check(st(w) == 'hidden', 'minimised: hidden')
w.root = R(viewable=False); check(st(w) == 'hidden', 'not on screen: hidden')
w._closed = True; check(st(w) == 'hidden', 'closed: hidden')
check("'front': 400, 'back': 1500" in src and "if st != 'hidden':" in src, 'live panel redraw: 0.6 s in use, 2 s behind, none minimised')
check("sig != getattr(self, '_chart_sig', None)" in src and "int(time.time() // 60)" in src, 'chart rebuild only on change, at least once a minute')

check('cv.restore_region(bg)  ' in src and 'restore_region(bg, bbox' not in src, 'live panel restores the whole background (a partial restore ghosts)')

pts = [mod._nm_attack_xyz(p[0]) for p in mod._NM_ATTACK_POOL]
check(len(set(pts)) == len(pts) and all(abs(x) > 5 or abs(z) > 5 for x, y, z in pts), 'simulated attackers each get their own spot away from the centre (not one blob)')
check(mod._nm_attack_xyz('198.51.100.7') == mod._nm_attack_xyz('198.51.100.7'), 'attacker position is stable between polls')
check("'x': 0, 'y': 0, 'z': 0,\n                'lat': _h['lat']" not in src, 'attack nodes are not placed at the origin')

# ── network counters never block the caller ──
import psutil as _psu
_orig = _psu.net_io_counters
_slow = {'n': 0}
def _slow_counters(*a, **k):
    _slow['n'] += 1
    if _slow['n'] > 2: time.sleep(4)
    return _orig(*a, **k)
_psu.net_io_counters = _slow_counters
t0 = time.time(); mod._nm_netio(); time.sleep(0.2)
tt, cc = mod._nm_netio()
check(cc is not None, 'counters: first reading arrives from the background thread')
time.sleep(1.5)
t1 = time.time(); mod._nm_netio(); mod._nm_netio(pernic=True); el = time.time() - t1
check(el < 0.2, 'counters: reading them returns at once even while the system call is stuck (%.3f s)' % el)
_psu.net_io_counters = _orig
check("now, c2 = _nm_netio()" in src and "psutil.net_io_counters()" not in src.split('def _update_live_traffic')[1].split('def _refresh_live_fast')[0], 'live panel reads the cached counters')

# ── stall watchdog on a real Tk loop ──
try:
    import tkinter as tk
    root = tk.Tk()
except Exception as e:
    print('  skip watchdog test (no display):', e); root = None
if root is not None:
    recs = []
    class H(logging.Handler):
        def emit(self, r): recs.append(r.getMessage())
    h = H(); mod.log.addHandler(h)
    mod._nm_start_stall_watchdog(root, limit_s=1.0)
    def block(): time.sleep(2.4)
    root.after(600, block)
    root.after(4500, root.quit)
    root.mainloop()
    mod.log.removeHandler(h)
    root.destroy()
    msgs = '\n'.join(recs)
    check('[stall] interface not responding' in msgs and 'block' in msgs, 'a frozen interface is logged with the code it is stuck in')
    check('[stall] interface was frozen for' in msgs, 'and its length is logged when it recovers')
    check(sum(1 for m in recs if 'not responding' in m) == 1, 'one dump per freeze (no log flood)')
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); sys.exit(1 if fails else 0)
