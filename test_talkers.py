#!/usr/bin/env python3
"""Top Talkers: the app keeps running totals that do not fade (per host: all bytes, sent, received, first seen), the
data feed carries them, and the new page builds, parses and has its controls.
Run: xvfb-run -a python3.12 test_talkers.py"""
import importlib.util, os, sys, re, time, shutil, subprocess, tempfile, threading
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import tkinter as tk
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
threading.Timer(90, lambda: os._exit(3)).start()

# ── running totals in the capture ──
root = tk.Tk(); root.withdraw()
ea = mod.EtherApeWindow(tshark_path=None, monitor=None)
ME, A, B = '192.168.1.164', '203.0.113.7', '203.0.113.9'
pk = [(A, ME, 'eth:ip:tcp', 1000)] * 30 + [(ME, A, 'eth:ip:tcp', 100)] * 10 + [(ME, B, 'eth:ip:udp', 500)] * 4
ea._pkt_queue.extend(pk)
ea._render_tick_inner()
for _ in range(400):                      # many ticks with no traffic: 'bytes' fades, the totals must not
    ea._render_tick_inner()
na, nb, nme = ea._nodes.get(A), ea._nodes.get(B), ea._nodes.get(ME)
check(na is not None and nb is not None and nme is not None, 'the three hosts are in the capture')
check(na and na['tot'] == 31000 and na['tx'] == 30000 and na['rx'] == 1000, 'host A: total 31000, sent 30000, received 1000 (%s)' % (na and (na['tot'], na['tx'], na['rx']),))
check(nme and nme['tot'] == 33000 and nme['tx'] == 3000 and nme['rx'] == 30000, 'this PC: total 33000, sent 3000, received 30000')
check(na and na['bytes'] < 31000 * 0.7, 'the old "bytes" figure has faded (%.0f), the totals have not' % (na['bytes'] if na else -1))
check(na and abs(na['t0'] - time.time()) < 60, 'first-seen time is recorded')
fl = ea._flows.get((A, ME, 'tcp'))
check(fl is not None and fl.get('tot') == 30000, 'the flow A -> this PC keeps its own total (30000)')

# ── the data feed ──
class Mon:
    config = {'web_port': 8765}
    def __getattr__(self, k): return lambda *a, **kw: None
srv = mod._ThreeDServer(Mon())
class FH:
    def _json(self, code, obj): self.out = (code, obj)
ea._ids_suspicious = {A}; ea._ids_reasons = {A: 'Port Scan: 41 ports in 10 s'}
h = FH(); srv._serve_topology3d(h)
d = h.out[1]; byid = {n['id']: n for n in d.get('nodes', [])}
check(h.out[0] == 200 and A in byid and 'now' in d, 'the feed answers with the hosts and the server time')
n = byid.get(A, {})
check(n.get('total') == 31000 and n.get('tx') == 30000 and n.get('rx') == 1000 and n.get('first_seen', 0) > 0, 'the feed carries total / sent / received / first seen')
check(n.get('why', '').startswith('Port Scan') and byid.get(B, {}).get('why') == '', 'a flagged host carries the reason, others carry none')
f = [x for x in d.get('flows', []) if x['src'] == A and x['dst'] == ME]
check(f and f[0].get('total') == 30000, 'flows carry their running total')

# ── the page ──
raw = srv._build_talkers_html()
html = raw.decode('utf-8') if isinstance(raw, bytes) else raw
check(len(html) > 25000 and '<title>NetSentinel Top Talkers</title>' in html, 'the Top Talkers page builds (%d bytes)' % len(html))
ids = ['streaks', 'vpnpill', 'sub', 'kHosts', 'kDn', 'kUp', 'kTot', 'kFlag', 'segWin', 'segRank', 'q', 'chips', 'hideLan', 'pauseBtn', 'csvBtn',
       'empty', 'main', 'rows', 'note', 'donut', 'leg', 'det', 'newl']
miss = [i for i in ids if len(re.findall(r'\bid="%s"' % i, html)) != 1]
check(not miss, 'every control is on the page once (%s)' % miss)
check(all(('data-w="%s"' % w) in html for w in ('live', '1m', '15m', '1h', 'session')) and all(('data-r="%s"' % r) in html for r in ('bytes', 'rate', 'packets', 'upload')),
      'time windows and rank-by switches are there')
body = html[:html.rindex('</script>')]
js = re.findall(r'<script>(.*?)</script>', html, flags=re.S)[0]
check("fetch('/api/topology3d'" in js and "'/api/whois?ip='" in js and "fetch('/api/'+a,{method:'POST'" in js, 'it reads the live feed and uses the whois and block functions the app already has')
check('CONFIRM BLOCK' in js and "ARM!==ip" in js, 'blocking needs a second press to confirm')
check('/3d#host=' in js, 'SHOW IN 3D links to the 3D view with the host')
check('t-last<33' in js and 'document.hidden' in js, 'the light trails are capped at 30 frames a second and pause when hidden')
node = shutil.which('node')
if node:
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tf:
        tf.write(js); pth = tf.name
    r = subprocess.run([node, '--check', pth], capture_output=True, text=True); os.unlink(pth)
    check(r.returncode == 0, 'the page script parses %s' % r.stderr.strip()[:160])
else:
    print('  skip  node is not installed: script syntax not checked here')
page3d = srv._build_3d_html().decode('utf-8')
check("/[#&]host=([^&]+)/.exec(location.hash" in page3d, 'the 3D view selects the host named in the link')
check('id="btnTopTalk" onclick="location.href=\'/talkers\'"' in page3d and 'id="btnTalkers" onclick="toggleTalkers()"' in page3d and 'FLOW TALKERS' in page3d,
      'in the 3D view, TOP TALKERS opens the page and FLOW TALKERS opens the ribbon diagram')
check('id="backBtn"' in html and 'history.back()' in js, 'Back on the page returns to where you came from')
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
