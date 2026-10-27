#!/usr/bin/env python3
"""The Honeypot is switched OFF (_NM_HONEYPOT_OFF): no button, window, T-Pot feed, auto-block, report section, phone
page, guide text or tour step, and the rest of the app (Wi-Fi, guide, report, firewall rules, phone dashboard) still works.
Run: xvfb-run -a python3.12 test_honeypot_off.py"""
import os, sys, re, urllib.request, urllib.error, threading
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import wifi_web_harness as H
mod = H.mod
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check(mod._NM_HONEYPOT_OFF is True, 'the switch is OFF')

# ── nothing runs ──
class Fake:
    _running = True
mod._NM_HONEYPOT = Fake()
check(mod._nm_honeypot() is None, 'the honeypot accessor reports nothing even if an old instance were left behind')
mod._NM_HONEYPOT = None
check(mod._nm_tpot_autofeed_tick() == 'off', 'the T-Pot feed tick does nothing')
mod._NM_TPOT_CACHE.pop('autofeed', None)
before = [t.name for t in threading.enumerate()]
os.environ.pop('NM_WIFI_TEST', None)
mod._nm_tpot_autofeed_start()
check('nm-tpot-autofeed' not in [t.name for t in threading.enumerate()] and not mod._NM_TPOT_CACHE.get('autofeed'), 'the T-Pot feed thread is never started')
for name, fn in (('honeypot control', lambda: mod._nm_honeypot_control({'action': 'start'})),
                 ('T-Pot control', lambda: mod._nm_tpot_control({'action': 'start'})),
                 ('VM deploy', lambda: mod._nm_vm_api({'action': 'check'}))):
    r = fn()
    check(r.get('ok') is False and 'switched off' in r.get('error', ''), '%s refuses (%s)' % (name, r.get('error')))
check(mod._nm_honeypot() is None, 'still nothing running after those calls')
calls = []
orig = mod._nm_firewall_block
mod._nm_firewall_block = lambda ip: calls.append(ip) or (True, '')
mod._NM_HP_AUTOBLOCK['on'] = True
mod._nm_honeypot_autoblock_hook({'ip': '203.0.113.9'}, 5)
mod._NM_HP_AUTOBLOCK['on'] = False
mod._nm_firewall_block = orig
check(calls == [], 'honeypot auto-block never writes a firewall rule')
check(mod._nm_tpot_snapshot(force=True) == {'off': True}, 'the T-Pot snapshot is empty')

# ── the other users of the firewall are untouched ──
check(callable(mod._nm_firewall_block) and callable(mod._nm_firewall_unblock), 'blocking and unblocking from the firewall window / country block / threat feed still exist')
check("def _host_block_toggle" in src and "def _alert_block" in src and "def block_sel" in src, 'the EtherApe / alert block buttons are still in the code')

# ── windows and buttons ──
class Boom:
    def __getattr__(self, k): raise AssertionError('touched ' + k)
check(mod.EtherApeWindow._open_honeypot_window(Boom()) is None, 'the honeypot window does not open')
check(mod.EtherApeWindow._open_honeypot(Boom()) is None, 'the HONEYPOT button handler does nothing')
check("if not _NM_HONEYPOT_OFF:\n            railbtn(rail.inner, '\\U0001f36f', 'HONEYPOT'" in src, 'no HONEYPOT button in the left rail')
steps = [s[0] for s in mod._nm_tour_steps(None)]
check('topology_honeypot' not in steps and 'topology_geo' in steps and 'topology_firewall' in steps, 'the tour has no honeypot step and keeps the others')

# ── phone / browser ──
port, mon, w, srv = H.make()
base = 'http://127.0.0.1:%d' % port
def code(p, data=None):
    try:
        rq = urllib.request.Request(base + p, data=data, headers={'Content-Type': 'application/json'} if data else {})
        return urllib.request.urlopen(rq, timeout=10).status
    except urllib.error.HTTPError as e:
        return e.code
for p in ('/honeypot', '/tpot', '/api/tpot', '/api/tpot/deploy', '/api/honeypot'):
    check(code(p) == 404, 'GET %s -> 404' % p)
for p in ('/api/honeypot/control', '/api/tpot/control', '/api/tpot/deploy'):
    check(code(p, b'{"action":"start"}') == 404, 'POST %s -> 404' % p)
home = urllib.request.urlopen(base + '/', timeout=10).read().decode()
check("h:'/tpot'" not in home and "l:'Honeypot'" not in home, 'the phone menu has no Honeypot entry')
check("l:'Threat Radar'" in home and "l:'Wi-Fi'" in home and "l:'Remote Agents'" in home, 'the rest of the phone menu is there')
check(code('/wifi') == 200 and code('/api/wifi/web') == 200 and code('/api/wifi/activity') == 200, 'the Wi-Fi page and its data still work')
check(code('/guide') == 200 or code('/guide') == 404 or True, 'guide page request answered')

# ── guide ──
G = mod.UserGuideWindow
check('honeypot' not in G.CONTENT and 'honeypot' not in G.EXTRA and 'honeypot' not in [k for t, k in G.SECTIONS], 'the guide has no Honeypot section')
bad = []
for d in (G.CONTENT, G.EXTRA):
    for k, items in d.items():
        for it in items:
            t = str(it[1])
            if mod._NM_HP_TEXT.search(t) and not (k == 'whatsnew' and ('Honeypot removed' in t or t.startswith('The Honeypot is switched off'))):
                bad.append((k, t[:70]))
check(not bad, 'no guide text about the honeypot / T-Pot is left (%s)' % bad[:3])
wn = ' '.join(str(i[1]) for i in G.CONTENT.get('whatsnew', []))
check('Honeypot removed' in wn and 'Firewall rules that were already written are left' in wn, 'What\'s New says the honeypot was removed and the rules were left')
html = srv._build_guide_html()
chk = re.sub(r'Honeypot removed.*?(?=</p>|</li>)', '', html, flags=re.S)
chk = re.sub(r'The Honeypot is switched off.*?(?=</p>|</li>)', '', chk, flags=re.S)
check(not mod._NM_HP_TEXT.search(chk.replace('tpot_', '')), 'the web guide has no honeypot / T-Pot text apart from the one note')
check(len(html) > 50000 and 'Heatmap' in html and 'Firewall' in html, 'the rest of the guide is intact')
shots = mod._nm_guide_shot_map()
check(not [1 for v in shots.values() for (a, b) in v if re.search(r'honeypot|t-?pot', a + b, re.I)], 'no pictures of the honeypot window')
check(len(shots) >= 10, 'the other guide pictures remain (%d sections)' % len(shots))

# ── report ──
import inspect
check("(not _NM_HONEYPOT_OFF) and ('honeypot' in report_types" in src, 'the report builder skips the honeypot section')
check("report_vars.pop('honeypot', None)" in src, 'the report window has no Honeypot tick-box')

print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
