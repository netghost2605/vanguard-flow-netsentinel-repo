#!/usr/bin/env python3
"""Closing the topology (EtherApe) window must not switch off the main window's timers.
It used to cancel the whole Tcl interpreter's list of timers, which stopped the clock, the live graphs and every other
window's refresh. Run: xvfb-run -a python3.12 test_ea_close_timers.py"""
import importlib.util, os, sys, time, threading
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
import tkinter as tk

root = tk.Tk()
ticks = []
def tick():
    ticks.append(time.time()); root.after(100, tick)
root.after(100, tick)
other = []
def other_chain():                      # a second, unrelated chain of timers, like another window's refresh
    other.append(time.time()); root.after(130, other_chain)
root.after(130, other_chain)
state = {}
threading.Timer(15, lambda: root.quit()).start()      # never hang, even if timers are dead

def make():
    state['ea'] = mod.EtherApeWindow(tshark_path=None, monitor=None)
def close():
    ea = state['ea']
    state['n_t'] = len(ticks); state['n_o'] = len(other)
    state['names'] = set(); 
    ea.root.tk.call(ea.root.protocol('WM_DELETE_WINDOW'))
    state['closed'] = True
def verdict():
    root.quit()
root.after(300, make); root.after(2500, close); root.after(4500, verdict)
root.mainloop()

check('ea' in state and state.get('closed'), 'the topology window opened and was closed')
check(len(ticks) - state['n_t'] >= 8, 'the main window clock timer keeps ticking after the close (%d ticks)' % (len(ticks) - state['n_t']))
check(len(other) - state['n_o'] >= 8, "another window's refresh timer keeps running after the close (%d ticks)" % (len(other) - state['n_o']))
try:
    n = len(root.tk.call('after', 'info'))
except Exception:
    n = -1
check(n >= 2, 'the interpreter still has its timers (%d)' % n)
check(not state['ea'].root.winfo_exists(), 'the topology window itself is gone')

# the helper cancels only the window's own timers
w = tk.Toplevel(root)
mine = []
def own(): mine.append(1)
w.after(150, own); w.after(150, own)
f = tk.Frame(w); f.pack(); f.after(150, own)
keep = []
root.after(150, lambda: keep.append(1))
n = mod._nm_cancel_window_afters(w)
check(n == 3, 'cancels exactly the three timers scheduled by the window and its child (%d)' % n)
t0 = time.time()
while time.time() - t0 < 0.5:
    root.update(); time.sleep(0.02)
check(not mine and keep, 'the window\'s callbacks never ran; the main window\'s did')
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check("self.root.tk.call('after','info')" not in src, "no code cancels the whole interpreter's timer list any more")
print('\nALL PASS' if not fails else '\nFAILED: %d' % len(fails))
sys.exit(1 if fails else 0)
