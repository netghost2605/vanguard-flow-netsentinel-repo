#!/usr/bin/env python3
"""The interface keeps ticking: the wake-up thread answers, the heartbeat runs, the stall report names what it should,
shutdown is clean, and the app's matplotlib figures no longer build a second hidden Tk window.
Run: xvfb-run -a python3.12 test_stall_pump.py"""
import importlib.util, os, sys, threading, time, logging, io
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

import tkinter as tk

# capture what the watchdog logs
buf = io.StringIO()
h = logging.StreamHandler(buf); h.setLevel(logging.DEBUG)
mod.log.addHandler(h)

root = tk.Tk()
st = mod._nm_start_stall_watchdog(root, limit_s=1.0)
check(isinstance(st, dict) and 'pump_n' in st, 'the watchdog hands back its state')

ticks = []
def tick():
    ticks.append(time.time())
    root.after(100, tick)
root.after(100, tick)
root.after(2500, root.quit)
t0 = time.time()
root.mainloop()
el = time.time() - t0
check(len(ticks) >= 15, 'ordinary timers run (%d ticks in %.1fs)' % (len(ticks), el))
check(st['pump_n'] >= 8, 'the wake-up thread got answers five times a second (%d in %.1fs)' % (st['pump_n'], el))
check(abs(st['lag']) < 0.5, 'the interface clock agrees with the real one (lag %.3f s)' % st['lag'])
check('[stall]' not in buf.getvalue(), 'no stall reported while the interface is healthy')

# a real stall: block the interface thread for ~2.3 s, the report must say what it was doing + what the threads were doing
buf.truncate(0); buf.seek(0)
def blocker():
    time.sleep(2.3)          # <- this is the line the report should name
root.after(50, blocker)
root.after(3600, root.quit)
root.mainloop()
out = buf.getvalue()
check('interface not responding' in out and 'blocker' in out, 'a stall is reported and names the code that blocked it')
check('wake-up thread last got an answer' in out, 'the report says whether the wake-up thread still got answers')
check('other threads:' in out and 'nm-wake' in out, 'the report lists what the other threads were doing')
check('interface was frozen for' in out, 'the recovery is reported')
check('Tcl has' in out and 'timer(s) waiting' in out, 'the report asks Tcl how many timers are waiting')

# clean shutdown: pump thread ends once the window is gone
n_before = st['pump_n']
root.destroy()
time.sleep(6.0)
alive = [t for t in threading.enumerate() if t.name == 'nm-wake' and t.is_alive()]
check(not alive, 'the wake-up thread ends when the window is destroyed')

# figures: no hidden second Tk interpreter any more
import matplotlib
matplotlib.use('TkAgg')
from matplotlib import _pylab_helpers
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
r2 = tk.Tk()
before = len(_pylab_helpers.Gcf.get_all_fig_managers())
fig = mod._nm_new_figure(figsize=(6, 3), facecolor='#010810')
ax = fig.add_subplot(111); ax.plot([1, 2, 3], [3, 1, 2])
cv = FigureCanvasTkAgg(fig, master=r2)
cv.get_tk_widget().pack(fill='both', expand=True)
r2.update(); cv.draw()
after = len(_pylab_helpers.Gcf.get_all_fig_managers())
check(after == before, 'new figure is not registered with pyplot (no hidden Tk window): %d -> %d' % (before, after))
check(cv.get_tk_widget().winfo_exists(), 'the figure shows inside the app window')
import matplotlib.pyplot as plt
plt.close(fig)   # what the EtherApe close path does: must not raise for an unmanaged figure
check(True, 'plt.close() on the unmanaged figure is harmless')
r2.destroy()

# the two build sites use the helper
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check('plt.figure(' not in src, 'no pyplot figure() calls left in the app')

print('\nALL PASS' if not fails else '\nFAILED: %d' % len(fails))
sys.exit(1 if fails else 0)
