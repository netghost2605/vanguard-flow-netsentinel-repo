"""The left rail fits the window: every button (incl. WI-FI, PREFS, QUIT) is fully visible at laptop heights."""
import importlib.util, os, sys, tkinter as tk
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
root = tk.Tk()
for H in (1100, 780, 700, 640):
    w = mod.ModernWindow.__new__(mod.ModernWindow)
    w._tk = tk
    top = tk.Toplevel(root); top.geometry('1392x%d+0+0' % H)
    w._main = tk.Frame(top, bg='black'); w._main.pack(fill='both', expand=True)
    w._build_sidebar()
    for _ in range(5):
        top.update(); top.update_idletasks()
    sbh = w._rail_frames[0].master.winfo_height()
    last = w._rail_frames[-1]
    bottom = last.winfo_y() + last.winfo_height()
    labels = [f.winfo_children()[0].cget('text').split('\n')[1] for f in w._rail_frames]
    hs = {f.winfo_height() for f in w._rail_frames}
    check(bottom <= sbh and 'WI-FI' in labels and labels[-2:] == ['PREFS', 'QUIT'],
          f'window {H}px: rail {sbh}px, button height {sorted(hs)}, QUIT ends at {bottom}px')
    top.destroy()
print('\nRESULT:', 'PASS' if not fails else 'FAIL %d' % len(fails))
os._exit(1 if fails else 0)
