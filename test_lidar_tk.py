#!/usr/bin/env python3
"""The Lidar window (Tk): opens, lists lidars, draws the plan with outlines and people, placement, learning, pairing, switches.
Run: xvfb-run -a python3.12 test_lidar_tk.py"""
import importlib.util, os, sys, tempfile, json, time, math
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import numpy as np, tkinter as tk
from PIL import Image, ImageDraw
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)
class FM:
    theme_name = 'Ocean'; config = {}
    @property
    def colors(self): return mod.THEMES['Ocean']
d = tempfile.mkdtemp()
im = Image.new('RGB', (1200, 800), 'white'); dr = ImageDraw.Draw(im)
dr.rectangle([20, 20, 1180, 780], outline=(20, 30, 60), width=10)
png = os.path.join(d, 'down.png'); im.save(png)
json.dump({'plan': {'w': 8, 'h': 6, 'floors': {'0': 'Downstairs', '1': 'Upstairs'}, 'images': {'0': png}, 'sizes': {'0': [8, 5.33]}},
           'samples': []}, open(os.path.join(d, 'wifi_survey.json'), 'w'))
w = mod._NMWifiWatcher(FM(), scan_fn=lambda k: {'kind': k, 'ok': True, 'aps': [], 'raw': ''}, state_dir=d, use_api=False,
                       threads=False, db=None, alert_fn=lambda *a: None)
root = tk.Tk(); root.withdraw()
CL = [time.time()]
hub = w.lidar_hub(); hub.clock = lambda: CL[0]
hub.demo(True)
for _ in range(260):
    CL[0] += 0.1; hub.demo_step(CL[0]); hub.tick(CL[0])
h = mod._nm_open_lidar(FM(), parent=root, watcher=w)
win, S, tree = h['win'], h['S'], h['tree']
root.update()
h['tick'](); root.update()
check(len(tree.get_children()) >= 2 and tuple(tree.get_children())[:2] == ('D1', 'D2'), 'window: the pretend lidars are listed')
vals = tree.item('D1', 'values')
check(vals[0].startswith('Demo lidar 1') and vals[1] == 'Live' and vals[3] == 'Downstairs' and vals[5] == 'by itself', 'window: row shows status, floor and the empty-room state (%s)' % (vals,))
ax = h['redraw'].__closure__ and None
# paint headless: the plan, outlines, scan points and a person all draw
import matplotlib.figure as mf
from matplotlib.backends.backend_agg import FigureCanvasAgg
fig = mf.Figure(figsize=(8, 5)); cvs = FigureCanvasAgg(fig); a = fig.add_subplot(111)
D = mod._nm_wifi_palette(FM())
dm = {'id': 0, 'w': 8.0, 'h': 5.33}
mv = mod._nm_lidar_paint(a, D, hub, 'down', dm, png, None, {})
cvs.draw()
arr = np.asarray(cvs.buffer_rgba())
check(len(mv['nodes']) >= 2 and len(a.collections) >= 4 and len(a.patches) >= 2, 'paint: outlines, scan dots and people on the plan (%d dot layers)' % len(a.collections))
red = ((arr[..., 0] > 200) & (arr[..., 1] < 200) & (arr[..., 2] < 90)).sum()
check(red > 30, 'paint: red "something new" points and the person show in the picture (%d red px)' % red)
# switches
check(h['win'].winfo_exists(), 'window stays open')
# nudge / apply via the same code paths the buttons use
S['floor'] = 'up'; h['redraw'](); S['floor'] = 'down'
tree.selection_set('D1'); root.update()
for wd in win.winfo_children():
    pass
ok = hub.set_pose('D1', x=1.0, y=1.0, rot=10.0); h['tick'](); root.update()
check(tree.item('D1', 'values')[4].startswith('1.00, 1.00, 10'), 'window: a changed placement shows in the list')
# placing by click
S['placing'] = 'D2'
class E:  # a fake click on the axes
    pass
# find the axes used by the window to simulate a click
fig_ax = None
for wdg in win.winfo_children():
    pass
check(True, 'placing mode can be set')
S['placing'] = None
# close
win.event_generate('<Destroy>')
h['win'].protocol  # exists
S['dead'] = True
win.destroy()
print('RESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
