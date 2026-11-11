#!/usr/bin/env python3
"""The redrawn 3D view: every control the page's script uses is still on the page, every button's handler exists,
the script parses, the page is told this PC's own address, and the new panels are there.
Run: python3.12 test_3d_skin.py"""
import importlib.util, os, sys, re, json, shutil, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

class Mon:
    config = {'web_port': 8765}
    def __getattr__(self, k): return lambda *a, **kw: None
srv = mod._ThreeDServer(Mon())
raw = srv._build_3d_html()
check(isinstance(raw, bytes) and len(raw) > 200000, 'the 3D page builds (%d bytes)' % len(raw))
html = raw.decode('utf-8')
check('@@' not in html.split('<script>')[0], 'no unfilled colour / build placeholders in the page head and markup')
check('<title>NetSentinel 3D Topology</title>' in html, 'the page has its new title')

# ── every control the old page had is still there, once ──
ids = ['c', 'hud', 'toolbar', 'vpnbanner', 'hn', 'hf', 'hp', 'hblocked', 'hbn', 'bldid', 'topN-sl', 'topN-val', 'spread-row',
       'spread-sl', 'spread-val', 'btnSpread', 'btnLabels', 'btnGrid', 'btnBlocked', 'bloomBtn', 'btnFS', 'btnTalkers', 'btnWifi',
       'fwbtn', 'worldbtn', 'atkbtn', 'killbtn', 'legend', 'info', 'urlboard', 'crosshair', 'wait', 'wait-msg', 'fwoverlay',
       'aioverlay', 'iIP', 'iDNS', 'iGeo', 'iOrg', 'iProto', 'iBytes', 'iPkts', 'iFlows', 'iBlocked', 'iSusp']
new_ids = ['nsTop', 'nsMix', 'nsDonut', 'nsPk', 'nsSide', 'nsTalk', 'nsTalkList', 'nsDock', 'iCap', 'iFlag', 'iName', 'iShare',
           'iBar', 'iTagLan', 'iTagHub', 'iTagProto']
cnt = lambda i: len(re.findall(r'\bid="%s"' % re.escape(i), html))
missing = [i for i in ids if cnt(i) != 1]
check(not missing, 'every control of the old page is on the new page exactly once (%s)' % missing)
missing = [i for i in new_ids if cnt(i) != 1]
check(not missing, 'the new panels are on the page: top bar, protocol mix, host card, busiest hosts, dock (%s)' % missing)

# ── every button's handler exists in the script ──
body = html[html.index('<body'):]
handlers = set(re.findall(r'on(?:click|input|contextmenu)="([A-Za-z_][A-Za-z0-9_]*)\(', body.split('<script')[0]))
scripts = re.findall(r'<script>(.*?)</script>', html, flags=re.S)
js = '\n'.join(scripts)
undef = [h for h in sorted(handlers) if not re.search(r'function\s+%s\s*\(|(?:window\.)?%s\s*=\s*(?:async\s*)?function|(?:const|let|var)\s+%s\s*=' % (h, h, h), js)]
check(len(handlers) >= 12 and not undef, 'all %d button handlers are defined in the script (%s)' % (len(handlers), undef))
for fn in ('_nsLayout', '_nsDecor', '_nsAnimate', '_nsCullLabels', '_nsRenderMix', '_nsRenderTalk', '_nsCard', 'toggleWorld',
           'showFw', 'toggleAttackMain', 'toggleKill', 'toggleTalkers', 'toggleWifi3D', 'selectNode', 'rebuildGeometry'):
    if not re.search(r'function\s+%s\s*\(' % fn, js):
        check(False, 'function %s is in the script' % fn)
check(True, 'the scene, layout and panel functions are in the script')

# ── the script parses (node, when it is installed) ──
node = shutil.which('node')
if node:
    bad = []
    for k, s in enumerate(scripts):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(s); p = f.name
        r = subprocess.run([node, '--check', p], capture_output=True, text=True)
        os.unlink(p)
        if r.returncode != 0:
            bad.append((k, r.stderr.strip()[:200]))
    check(not bad, 'every script block on the page parses (%d blocks) %s' % (len(scripts), bad[:1]))
else:
    print('  skip  node is not installed: script syntax not checked here')

# ── no blur over the 3D canvas (it would be recomputed every frame) ──
skin = html[html.index('NS skin (glass chrome)'):html.index('</style>')]
live_blur = [m for m in re.findall(r'backdrop-filter:\s*([^;}!]+)', skin) if m.strip() != 'none']
check(not live_blur, 'the new panels use no backdrop blur over the 3D canvas (%s)' % live_blur[:2])

# ── the page is told this PC's own address (it sits in the middle) ──
class FakeHandler:
    def __init__(self): self.out = None
    def _json(self, code, obj): self.out = (code, obj)
h = FakeHandler()
srv._serve_topology3d(h)
check(h.out and h.out[0] == 200 and 'self_ip' in h.out[1] and 'nodes' in h.out[1] and 'flows' in h.out[1],
      'the topology data carries self_ip next to nodes and flows')
t = {'n': 0}
orig = mod._nm_local_ipv4
mod._nm_local_ipv4 = lambda *a, **k: (t.__setitem__('n', t['n'] + 1) or '192.0.2.10')
mod._NM_SELF_IP.update({'ip': '', 't': 0.0})
a = mod._nm_self_ip_cached(); b = mod._nm_self_ip_cached(); c = mod._nm_self_ip_cached()
mod._nm_local_ipv4 = orig
check(a == b == c == '192.0.2.10' and t['n'] == 1, 'this PC\'s address is looked up once and then cached (lookups: %d)' % t['n'])

# ── smooth motion, no floor bars, fps readout ──
check('const _NS_FLOOR_BARS=false;' in js and 'if(!_NS_FLOOR_BARS){m.visible=false;' in js, 'the protocol bars on the floor are switched off')
check('t+=0.016;' not in js and '_nsStep=_dt/0.016; t+=_dt;' in js and 'rotY+=0.0009*_nsStep' in js,
      'motion follows the real time between frames, not the frame count')
check(cnt('hfps') == 1, 'the top bar shows frames per second')

# ── this PC's several addresses (Wi-Fi + Ethernet) are all the centre ──
check('_nsSelfSet=new Set((d.self_ips||[])' in js and 'if(n===hub||_nsSelfSet.has(n.id)){n.x=0;n.y=0;n.z=0;' in js,
      "all of this PC's addresses sit in the centre, the busiest is the hub")
check('self_ips' in h.out[1] and isinstance(h.out[1]['self_ips'], list), 'the topology data lists all of this PC\'s addresses')

# ── guide ──
G = mod.UserGuideWindow
wn = ' '.join(str(i[1]) for i in G.CONTENT.get('whatsnew', []))
check('3D view: new look' in wn and 'Nothing was removed' in wn, "What's New describes the new 3D view")
allg = ' '.join(str(i[1]) for d in (G.CONTENT, G.EXTRA) for v in d.values() for i in v)
check('immediately right of the protocol legend' not in allg and 'in the dock along the bottom' in allg,
      'the guide says where the 3D buttons are now')

print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
