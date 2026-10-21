#!/usr/bin/env python3
"""The desktop cube: geometry, picking, drawing, window finding. Run: xvfb-run -a python3 test_cube.py"""
import importlib.util, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import numpy as np
from PIL import Image
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

# every face points outward and its corners go round the right way (top-left, top-right, bottom-right, bottom-left)
for key in mod._NM_CUBE_GEOM:
    n, pts, size = mod._nm_cube_corners(key)
    cen = pts.mean(axis=0)
    check(float(n @ cen) > 0, f'{key}: normal points away from the centre')
    e1, e2 = pts[1] - pts[0], pts[3] - pts[0]
    check(float(np.cross(e1, e2) @ n) < 0 or float(np.cross(e1, e2) @ n) > 0, f'{key}: corners form a plane')
    # seen from outside, top-left -> top-right -> bottom-right must run clockwise (texture not mirrored)
    cr = np.cross(pts[1] - pts[0], pts[2] - pts[1])
    check(float(cr @ n) < 0, f'{key}: texture is not mirrored')
# homography maps the corners it was given
dst = [(10, 12), (210, 20), (200, 120), (5, 110)]
src = [(0, 0), (100, 0), (100, 50), (0, 50)]
co = mod._nm_cube_homography(dst, src)
for (x, y), (u, v) in zip(dst, src):
    d = co[6] * x + co[7] * y + 1
    uu, vv = (co[0] * x + co[1] * y + co[2]) / d, (co[3] * x + co[4] * y + co[5]) / d
    check(abs(uu - u) < 1e-6 and abs(vv - v) < 1e-6, f'homography maps {dst.index((x, y))}')
# drawing: the front face is seen head-on, and a click on it finds it
tex = {k: Image.new('RGB', mod._NM_CUBE_GEOM[k][2], (80 + 20 * i, 60, 60)) for i, k in enumerate(mod._NM_CUBE_GEOM)}
size = (800, 450)
bg = mod._nm_cube_background(size)
img, hits = mod._nm_cube_render(size, mod._nm_cube_rot(0, 0), 6.8, tex, bg)
check(img.size == size, 'frame has the asked size')
check([k for k, _ in hits] == ['main'], 'looking straight on shows only the front face')
check(mod._nm_cube_pick(hits, 400, 225) == 'main', 'click in the middle picks the front face')
check(mod._nm_cube_pick(hits, 5, 5) is None, 'click on the background picks nothing')
img, hits = mod._nm_cube_render(size, mod._nm_cube_rot(0.3, -0.6), 6.8, tex, bg)
check(len(hits) == 3, 'turned a little, three faces show')
img, hits = mod._nm_cube_render(size, mod._nm_cube_rot(0, np.pi), 6.8, tex, bg)
check([k for k, _ in hits] == ['heatmap'], 'turned round, the back face (heatmap) shows')
img, hits = mod._nm_cube_render(size, mod._nm_cube_rot(np.pi / 2, 0), 6.8, tex, bg)
check([k for k, _ in hits] == ['wifi'], 'tipped forward, the top face (Wi-Fi) shows')
img, hits = mod._nm_cube_render(size, mod._nm_cube_rot(-np.pi / 2, 0), 6.8, tex, bg)
check([k for k, _ in hits] == ['lidar'], 'tipped back, the bottom face (Lidar) shows')
# a face texture with and without a picture
t1 = mod._nm_cube_face_texture('main', 'Main dashboard', Image.new('RGB', (1400, 820), (200, 0, 0)))
t2 = mod._nm_cube_face_texture('wifi', 'Wi-Fi', None, 'not open - click to open')
check(t1.size == (1024, 576) and t2.size == (768, 768), 'face pictures have the right sizes')
# the real window: window finding, button, startup windows
import tkinter as tk
root = tk.Tk(); root.title('main')
tl = {}
for t in ('◈  EtherApe — Network Topology Monitor', 'Lidar — room map and people', 'Something else'):
    w = tk.Toplevel(root); w.title(t); tl[t] = w
class Owner: pass
o = Owner(); o.root = root; o._cube = None
cube = mod._NmCube(o, capture=lambda h: Image.new('RGB', (900, 500), (30, 90, 30)), hwnd_of=lambda w: 1)
root.update()
check(cube.targets['topology'][0] is not None and cube.targets['lidar'][0] is not None, 'windows are found by part of their title')
check(cube.targets['wifi'][0] is None and 'not open' in cube.targets['wifi'][1], 'a window that is not open says so')
tl['Something else'].destroy()
t_end = time.time() + 2.0
while time.time() < t_end:
    root.update(); time.sleep(0.02)
check(cube._out is not None and cube._out_id > 3, 'cube draws frames on its own thread')
cube._press(type('E', (), {'x': 100, 'y': 100})()); cube._drag(type('E', (), {'x': 160, 'y': 130})())
check(abs(cube.R - mod._nm_cube_rot(0, 0)).max() > 0.01, 'dragging turns the cube')
cube._release(type('E', (), {'x': 160, 'y': 130})())
d0 = cube._dist_goal; cube._zoom(0.5); cube._zoom(0.5); cube._zoom(0.5); cube._zoom(0.5)
check(cube._dist_goal >= 4.6, 'zoom stops before the camera is inside the cube')
cube.close(); root.update()
check(cube._stop.is_set() and o._cube is None, 'closing stops the threads and clears the handle')
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check("command=self._open_cube" in src and "CUBE" in src, 'CUBE button is in the top bar')
check(src.index("self._bloom_btn.pack(side='left', pady=0, ipady=14)") < src.index("command=self._open_cube"), 'CUBE button sits right after BLOOM')
check("self.root.after(2200, self._open_heatmap)" in src and "self.root.after(3400, self._open_floor)" in src, 'heatmap and floor open at start-up')
check("'startup_windows'" in src, 'start-up windows can be turned off in Settings')
print('ALL PASS' if not fails else 'FAILED: %d' % len(fails)); os._exit(1 if fails else 0)
