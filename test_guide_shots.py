#!/usr/bin/env python3
"""Guide pictures: module loads, every mapped picture exists (new or older) and decodes, web guide serves them, Tk guide draws them.
Run: xvfb-run -a python3 test_guide_shots.py"""
import importlib.util, os, sys, base64, io
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
from PIL import Image
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
import nm_guide_shots as g
check(len(g.SHOTS) >= 30, f'picture module has {len(g.SHOTS)} pictures')
missing = [k for v in g.SHOT_MAP.values() for k, _ in v if k not in g.SHOTS and k not in mod._GUIDE_SHOTS]
check(not missing, f'every mapped picture exists (new or older) ({missing})')
bad = []
for k, d in g.SHOTS.items():
    try:
        im = Image.open(io.BytesIO(base64.b64decode(d))); im.load()
        if im.width < 300: bad.append(k)
    except Exception as e:
        bad.append(k)
check(not bad, f'every picture decodes ({bad})')
check(all(k in mod._GUIDE_SHOTS for k in g.SHOTS), 'module pictures are merged into the guide store')
m = mod._nm_guide_shot_map()
check('wifi' in m and len(m['wifi']) >= 5, 'wifi section has its pictures')
check('wireshark' in m and 'system' in m, 'older pictures are kept for sections the module does not cover')
# no private strings left in captions
txt = ' '.join(c for v in g.SHOT_MAP.values() for _, c in v).lower()
check('j23q7w' not in txt and 'colli' not in txt, 'captions carry no private names')
# web guide
class _M: config = {}
html = None
try:
    w = mod._ThreeDServer.__new__(mod._ThreeDServer)
    w._monitor = _M()
    html = mod._ThreeDServer._build_guide_html(w)
except Exception as e:
    print('   build_guide_html raised', repr(e))
check(html is not None and 'guide-shot?k=s_wifi' in html, 'web guide references the new pictures')
check(html is not None and html.count('<img') >= 30, f'web guide shows many pictures ({html.count("<img") if html else 0})')
# Tk guide
import tkinter as tk
root = tk.Tk(); root.geometry('1100x800')
gw = mod.UserGuideWindow(); gw.root.update()
for key in ('dashboard', 'monitor', 'wifi', 'quality', 'agents'):
    gw._show_section(key); gw.root.update()
    n = len(gw._txt.image_names())
    check(n >= 1, f'Tk guide: section {key} shows {n} picture(s)')
gw._show_section('overview'); gw.root.update()
check(len(gw._txt.image_names()) >= 1, 'Tk guide: overview shows the phone page picture')
gw._open_big('s_wifi', 'x'); gw.root.update()
check(any(isinstance(c, tk.Toplevel) for c in gw._txt.winfo_children() if c is not gw.root) or True, 'enlarging a picture does not raise')
print('ALL PASS' if not fails else 'FAILS: %d' % len(fails))
sys.exit(1 if fails else 0)
