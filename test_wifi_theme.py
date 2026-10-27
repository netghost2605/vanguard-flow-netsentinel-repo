#!/usr/bin/env python3
"""The Wi-Fi window follows the app theme: colours at open, and a theme change reaches an open window in place.
Run: xvfb-run -a python3.12 test_wifi_theme.py"""
import importlib.util, os, sys, time, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import tkinter as tk
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)
class FM:
    def __init__(self): self.theme = 'Crimson'; self.config = {}
    @property
    def colors(self): return mod.THEMES[self.theme]
fm = FM(); root = tk.Tk(); root.withdraw(); sd = tempfile.mkdtemp()
w = mod._NMWifiWatcher(fm, scan_fn=lambda k: {'kind': k, 'ok': True, 'aps': [], 'raw': ''}, state_dir=sd, use_api=False,
                       threads=False, db=None, alert_fn=lambda *a: None)
win = mod._nm_open_wifi(fm, watcher=w, state_dir=sd); root.update()
st = win._nm_state; D = st['D']; C = mod.THEMES['Crimson']
check(D['bg'] == C['bg'] and D['accent'] == C['download'], 'opens in the active theme (Crimson)')
check(str(win.cget('bg')).lower() == C['bg'], 'window background is the theme background')
check(str(st['nb'].cget('style')) == 'NMW.TNotebook', 'tabs use the Wi-Fi window\'s own themed style')
from tkinter import ttk
sty = ttk.Style(win)
check(str(sty.lookup('NMW.TButton', 'background')).lower() == C['panel'], 'buttons use the theme panel colour')
check(str(sty.lookup('TButton', 'background')).lower() != C['panel'], "the rest of the app's buttons are untouched")
lw = st['lwalk']; check(lw._colors == (D['well'], D['accent']), 'the walking man glows in the theme accent')
chip_bg0 = None
def find_labels(wd, out):
    for c in wd.winfo_children():
        if c.winfo_class() == 'Label': out.append(c)
        find_labels(c, out)
labs = []; find_labels(win, labs)
n_bg_old = sum(1 for l in labs if str(l.cget('bg')).lower() == C['bg'])
fm.theme = 'Neon'; N = mod.THEMES['Neon']
t_end = time.time() + 3.0
while time.time() < t_end: root.update(); time.sleep(0.01)
check(D['bg'] == N['bg'] and D['accent'] == N['download'], 'a theme change is picked up within 2 s')
check(str(win.cget('bg')).lower() == N['bg'] and sum(1 for l in labs if str(l.cget('bg')).lower() == C['bg']) == 0 and n_bg_old > 0,
      f'every label on the old background was recoloured ({n_bg_old} labels)')
check(str(sty.lookup('NMW.TButton', 'background')).lower() == N['panel'], 'buttons recoloured')
check(lw._colors == (D['well'], D['accent']), 'the walking man is recoloured (the ESP32 tab and its second man are switched off)')
win.destroy(); root.update()
print('RESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
