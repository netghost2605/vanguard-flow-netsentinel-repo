#!/usr/bin/env python3
"""Live Threat Map page: Radware embed + traffic overlay. Run: python3 test_livemap.py"""
import importlib.util, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
html = mod._ThreeDServer._build_livemap_html(type('X', (), {'_monitor': None})())
check('livethreatmap.radware.com' in html and '<iframe id="fr"' in html, 'embeds Radware\'s page in an iframe')
check('id="ov"' in html and 'pointer-events:none' in html, 'overlay canvas sits on top and does not block the map underneath')
check('/api/topology3d' in html and '/api/threats' in html, 'draws the app\'s own traffic and threat feeds')
check('Calibrate overlay' in html and 'Reference pins' in html and 'nm_livemap' in html, 'calibration with reference pins, remembered per browser')
check("value=\"app\"" not in html and "setMap('app')" in html and '/world-map.jpg' in html, 'App map fallback uses the app\'s own world map')
check('@@' not in html, 'theme tokens all replaced')
check(not re.search(r'(fetch|XMLHttpRequest)\([^)]*radware', html, re.I), 'no request is made to read Radware\'s data, only the page is shown')
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check("path == '/livemap'" in src and "_open_livemap" in src and "Live Threat Map', lambda" in src, 'route, desktop opener and Geo Map button exist')
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); sys.exit(1 if fails else 0)
