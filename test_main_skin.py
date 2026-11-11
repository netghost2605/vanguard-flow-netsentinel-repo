#!/usr/bin/env python3
"""The restyled main window: it builds, refreshes with data without errors, keeps every control, and the four
headline cards plus TODAY are equal width. Run: xvfb-run -a python3.12 test_main_skin.py"""
import importlib.util, os, sys, time, datetime, random
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import tkinter as tk
from tkinter import ttk
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

random.seed(3)
now = datetime.datetime.now()
ts = [(now - datetime.timedelta(minutes=5 * i)).isoformat() for i in range(30, -1, -1) if (now - datetime.timedelta(minutes=5 * i)).date() == now.date()]
n = len(ts)
dl = [300 + random.random() * 200 for _ in range(n)]; ul = [60 + random.random() * 40 for _ in range(n)]
pg = [10 + random.random() * 20 for _ in range(n)]; dv = [5 + random.random() * 30 for _ in range(n)]
class Mon:
    config = {'web_port': 8765}
    colors = {'download': '#2bff5c', 'upload': '#ff2d55', 'ping': '#19c3ff', 'dns': '#ffb300'}
    _interval_minutes = 5; _running_dns = False; _db_load_ok = True; _db = object(); _speedtest_exe = HERE; _tshark_exe = HERE
    def _load_data(self): return {'download': dl, 'upload': ul, 'ping': pg, 'dns_values': dv, 'timestamps': ts, 'dns_timestamps': ts}
    def _test_busy(self): return False
    def __getattr__(self, k): return lambda *a, **kw: None
W = mod.ModernWindow
w = W.__new__(W)
w._tk = tk; w._ttk = ttk; w._monitor = Mon(); w._closed = False
w._spk = {'dl': [], 'ul': [], 'pg': [], 'dns': []}; w._gauge_refs = {}; w._stat_labels = {}; w._axes = {}
w._mpl_canvas = None; w._mpl_fig = None; w._view_mode = 'today'; w._hist_offset = 0; w._bloom_enabled = True
w.root = tk.Tk(); mod._nm_pick_mono(w.root); w.root.geometry('1400x820+0+0')
errs = []
w.root.report_callback_exception = lambda *a: errs.append(repr(a[1]))
try:
    w._build_ui()
except Exception as e:
    errs.append('build ' + repr(e))
check(not errs, 'the main window builds (%s)' % errs[:1])
for _ in range(3):
    w.root.update()
    try: w._do_refresh()
    except Exception as e: errs.append('refresh ' + repr(e))
    w.root.update(); time.sleep(0.2)
check(not errs, 'it refreshes with data without errors (%s)' % errs[:2])
check(set(w._gauge_refs) == {'dl', 'ul', 'pg', 'dns'} and all({'val', 'bar_bg', 'bar_fill', 'spk', 'dot', 'val_lbl', 'strip', 'sub'} <= set(r) for r in w._gauge_refs.values()),
      'the four headline cards are there with value, bar, sparkline and the new average line')
check(n < 1 or all('avg ' in r['sub'].get() and 'max ' in r['sub'].get() for r in w._gauge_refs.values()), 'each card shows today\'s average and maximum (%s)' % w._gauge_refs['dl']['sub'].get())
check(w._gauge_refs['dl']['val'].get() == '%.1f' % dl[-1], 'the download card shows the latest value')
check(set(w._stat_labels) == {'tests', 'dns_n', 'max_dl', 'jitter'} and w._stat_labels['tests'].get() == str(n), 'the TODAY card is still there (tests: %s)' % w._stat_labels['tests'].get())
cards = [w._gauge_refs[k]['strip'].master for k in ('dl', 'ul', 'pg', 'dns')]
widths = [c.winfo_width() for c in cards]
check(max(widths) - min(widths) <= 2 and min(widths) > 150, 'the headline cards are equal width and all on screen (%s)' % widths)
check(cards[-1].winfo_rootx() + widths[-1] < w.root.winfo_rootx() + w.root.winfo_width(), 'the DNS card is not pushed off the window')
check(set(w._axes) == {'dl', 'ul', 'pg', 'live', 'dns', 'stats'} and w._axes['dl'].get_title(loc='left') == 'Download', 'the six chart panels are there')
check(set(w._view_btns) == {'today', 'week', 'month', 'all'} and set(w._nav_btns) == {'Dashboard', 'System', 'Pen Test'}, 'the range and page switches are there')
w._set_view('week'); check(w._view_btns['week'].cget('fg') == W.ACC and w._view_btns['today'].cget('fg') == W.TICK, 'choosing This Week highlights it')
w._set_view('today')
labels = [f.winfo_children()[0].cget('text').split('\n')[1] for f in w._rail_frames]
check(len(labels) == 19 and labels[:2] == ['RUN', 'DNS'] and labels[-2:] == ['PREFS', 'QUIT'] and 'WI-FI' in labels and 'TOPOLOGY' in labels, 'the rail has its 19 buttons in order (%d)' % len(labels))
w._monitor.colors = dict(Mon.colors, download='#ff00ff'); w._apply_gauge_colors()
check(w._gauge_refs['dl']['strip'].cget('bg') == '#ff00ff' and w._gauge_refs['dl']['val_lbl'].cget('fg') == '#ff00ff', 'a new colour theme recolours the card, including its edge strip')
b0 = w._bloom_enabled; w._toggle_bloom(); w._toggle_bloom()
check(w._bloom_enabled == b0 and not errs, 'the BLOOM switch still works')
check(set(w._status_dots) == {'speedtest', 'tshark', 'web', 'db'} and 'Next test' in w._next_var.get(), 'the status bar shows its items and the countdown')
check(mod._nm_blend('#000000', '#ffffff', 0.5) in ('#808080', '#7f7f7f'), 'colour mixing for the soft sparkline fill works')
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
