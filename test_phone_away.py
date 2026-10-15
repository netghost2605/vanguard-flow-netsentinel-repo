#!/usr/bin/env python3
"""Phone alerts and automatic Away: presence tracking (fake ARP), Away rules, PHONE events, the movement picture,
ntfy requests (picture + non-ASCII headers), and the dialog (xvfb). Run: xvfb-run -a python3.12 test_phone_away.py"""
import importlib.util, os, sys, time, tempfile, json
TMPH = tempfile.mkdtemp(); os.environ['HOME'] = TMPH; os.environ['USERPROFILE'] = TMPH
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)

check(mod._nm_mac_norm('AA-BB-CC-dd-ee-ff') == 'aa:bb:cc:dd:ee:ff' and mod._nm_mac_norm('xyz') == '', 'MAC addresses normalised')
import subprocess as _sp
_orig_run, _orig_win = _sp.run, mod._NM_IS_WIN
class _RR: stdout = '''
Interface: 192.168.1.101 --- 0x9
  Internet Address      Physical Address      Type
  192.168.1.23          12-34-56-78-9a-bc     dynamic
  192.168.1.254         a0-2d-db-d6-d5-61     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
'''
_sp.run = lambda *a, **k: _RR(); mod._NM_IS_WIN = True
t = mod._nm_arp_macs()
_sp.run = _orig_run; mod._NM_IS_WIN = _orig_win
check(t == {'12:34:56:78:9a:bc': '192.168.1.23', 'a0:2d:db:d6:d5:61': '192.168.1.254'}, f'Windows ARP table parsed as {{mac: ip}} (dynamic only): {t}')
check(mod._NMPhonePresence('aa:bb:cc:00:00:01').table is mod._nm_arp_macs, 'the presence tracker uses the {mac: ip} table (not the LAN scan\'s {ip: mac} one)')
# ── presence with a fake network ─────────────────────────────────────────
clk = [1000.0]; net = {'aa:bb:cc:00:00:01': '192.168.1.23'}; calls = {'sweep': 0, 'probe': 0}
def probe(ip):
    calls['probe'] += 1
    for m, i in net.items():
        if i == ip: return m.replace(':', '-').upper()
    return None
def sweep():
    calls['sweep'] += 1; return dict(net)
P = mod._NMPhonePresence('AA:BB:CC:00:00:01', probe=probe, table=lambda: {}, sweep=sweep, clock=lambda: clk[0])
check(P.home(10) is True, 'before the first look: counted as home (no false Away right after start)')
check(P.check() and P.ip == '192.168.1.23' and calls['sweep'] == 1, 'found by sweeping the network, IP remembered')
s0 = calls['sweep']; clk[0] += 30; check(P.check() and calls['sweep'] == s0, 'next check asks the known IP directly (no sweep)')
net = {'aa:bb:cc:00:00:01': '192.168.1.40'}; clk[0] += 30
check(not P.check() or P.ip == '192.168.1.40', 'IP changed: the old IP no longer answers')
clk[0] += 200; check(P.check() and P.ip == '192.168.1.40', 'IP changed: found again by the next sweep')
net = {}; t_gone = clk[0]
for k in range(25):
    clk[0] += 30; P.check()
    if clk[0] - t_gone < 9 * 60: assert P.home(10), 'home for the first 10 minutes'
check(P.home(10) is False, 'gone for more than 10 minutes: away')
net = {'aa:bb:cc:00:00:01': '192.168.1.40'}; clk[0] += 30; P.check(); check(P.home(10), 'back: home at the next check')

# ── watcher rules ─────────────────────────────────────────────────────────
class FakeP:
    def __init__(self, mac): self.mac = mac; self.present = True; self.last_seen = 0.0; self.ip = '192.168.1.23'; self.n = 0
    def check(self): self.n += 1; self.last_seen = time.time() if self.present else self.last_seen; return self.present
    def home(self, minutes=10): return self.present
alerts = []
idle = [5000.0]
w = mod._NMWifiWatcher(None, scan_fn=lambda k: {'kind': k, 'ok': True, 'aps': [], 'raw': ''}, state_dir=tempfile.mkdtemp(),
                       use_api=False, threads=False, db=None,
                       alert_fn=lambda t, m, s, image=None: alerts.append((t, m, s, image)), idle_fn=lambda: idle[0])
w.set_pref('auto_away_min', 10)
check(w.is_away() is True, 'no phone chosen: an idle PC still counts as away (old behaviour)')
w.phone_factory = FakeP
w.set_pref('phone_mac', 'aa:bb:cc:00:00:01'); w.set_pref('phone_name', "Trevor's phone")
w.phone_tick(); check(w.is_away() is False, 'phone at home: NOT away, even though the PC has been idle (no alerts at night)')
w.phone.present = False; w.phone_tick(); time.sleep(0.3)
check(w.is_away() is True, 'phone gone: away')
check(any(e['kind'] == 'PHONE' and 'left' in e['detail'] for e in w.events) and any(a[0] == 'Away mode' for a in alerts),
      'leaving: a PHONE event and a phone alert ("Away mode")')
idle[0] = 10.0; check(w.is_away() is False, 'phone gone but someone is using the PC: not away')
idle[0] = 5000.0
w.phone.present = True; w.phone_tick(); time.sleep(0.3)
check(w.is_away() is False and any('back home' in e['detail'] for e in w.events), 'back: Away off, event says so')
w.set_pref('phone_notify', False); n = len(alerts); w.phone.present = False; w.phone_tick(); time.sleep(0.3)
check(len(alerts) == n and w.is_away(), 'phone notices can be switched off (Away still follows the phone)')
w.phone.present = True; w.phone_tick()
w.set_pref('away', True); check(w.is_away() is True, 'the Away tick box still forces Away (when the PC is idle)')
w.set_pref('away', False)
pi = w.phone_info(); check(pi['name'] == "Trevor's phone" and pi['home'] is True and pi['mac'] == 'aa:bb:cc:00:00:01', 'phone info for the pages')
check(w.web_view()['phone']['home'] is True, 'web view carries the phone state')
w.set_pref('phone_mac', ''); check(w.phone_state() is None and w.phone_info() is None, 'stop following: no phone state')

# ── the movement picture on alerts ────────────────────────────────────────
now = time.time()
for i in range(120, 0, -1):
    lv = 0.05 + (0.3 if 30 < i < 60 else 0.0)
    w.csi_hist.append((now - i, lv, 0.12, lv > 0.12, -50))
png = w.snapshot_png(); check(png is not None and png[:8] == b'\x89PNG\r\n\x1a\n' and len(png) > 3000, f'movement picture is a PNG ({len(png or b"")} bytes)')
alerts.clear(); w.event('MOVEMENT', 'ESP32 boards: movement detected — while you are away', alert=True, key='mvtest'); time.sleep(1.5)
check(alerts and alerts[-1][0] == 'Movement while you are away' and alerts[-1][3] and alerts[-1][3][:4] == b'\x89PNG',
      'a movement alert carries the picture')
w.set_pref('alert_image', False); alerts.clear(); w.event('MOVEMENT', 'x', alert=True, key='mvtest2'); time.sleep(1.0)
check(alerts and alerts[-1][3] is None, 'picture can be switched off')
old3 = []; w.alert_fn = lambda t, m, s: old3.append(t); w.event('MOVEMENT', 'y', alert=True, key='mvtest3'); time.sleep(1.0)
check(old3 == ['Movement while you are away'], 'an alert handler without the picture argument still works')

# ── ntfy requests ─────────────────────────────────────────────────────────
check(mod._nm_hdr('plain') == 'plain' and mod._nm_hdr('a — b').startswith('=?UTF-8?B?'), 'non-ASCII header text is encoded (it used to make urllib refuse to send)')
mod._nm_notify_config_save({'backend': 'ntfy', 'ntfy_topic': 'vanguard-test', 'ntfy_server': 'https://ntfy.example', 'min_sev': 'warn'})
sent = []
import urllib.request as UR
class R:
    def read(self): return b'{}'
orig = UR.urlopen
UR.urlopen = lambda req, timeout=10: (sent.append(req), R())[1]
ok, why = mod._nm_notify('Movement while you are away', 'boards — living room', 'warn', 'wifi', attach=png)
r = sent[-1]
check(ok and r.get_method() == 'PUT' and r.full_url == 'https://ntfy.example/vanguard-test' and r.data == png
      and r.get_header('Filename') == 'graph.png' and r.get_header('Message').startswith('=?UTF-8?B?'),
      'ntfy: picture sent as the body (PUT), text in an encoded Message header')
ok, why = mod._nm_notify('Tést', 'plain text', 'warn', 'wifi')
check(ok and sent[-1].get_method() == 'POST' and sent[-1].data == b'plain text', 'ntfy: text-only alert is a POST with the text')
UR.urlopen = orig

# ── the dialog ────────────────────────────────────────────────────────────
import tkinter as tk
root = tk.Tk(); root.withdraw()
mod._nm_notify_config_save({})
fake_net = {'aa:bb:cc:00:00:01': '192.168.1.23', '12:34:56:78:9a:bc': '192.168.1.50', '00:11:22:33:44:55': '192.168.1.254'}
w2 = mod._NMWifiWatcher(None, scan_fn=lambda k: {'kind': k, 'ok': True, 'aps': [], 'raw': ''}, state_dir=tempfile.mkdtemp(),
                        use_api=False, threads=False, db=None, alert_fn=lambda *a, **k: None, idle_fn=lambda: 0)
w2.phone_factory = FakeP
dlg = mod._nm_phone_dialog(root, mod._NM_WIFI_DASH, w2, scan=lambda: dict(fake_net),
                           hostname=lambda ip: {'192.168.1.50': 'iPhone', '192.168.1.254': 'router'}.get(ip, ''))
root.update()
check('OFF' in dlg['st_var'].get(), 'alerts: shows OFF when not set up')
dlg['setup'](); cfg = mod._nm_notify_config()
check(cfg.get('backend') == 'ntfy' and cfg.get('ntfy_topic', '').startswith('vanguard-') and len(cfg['ntfy_topic']) >= 20
      and 'ON' in dlg['st_var'].get(), f"alerts: one click makes a private ntfy topic ({cfg.get('ntfy_topic')})")
dlg['scan'](); t_end = time.time() + 5
while time.time() < t_end and not dlg['S']['found']: root.update(); time.sleep(0.05)
rows = dlg['S']['found']
check(len(rows) == 3 and rows[1]['name'] == 'iPhone' and rows[1]['private'] and not rows[2]['private'], 'devices listed with names, phones flagged "private address"')
fake_net['aa:bb:cc:99:99:99'] = '192.168.1.77'; dlg['scan'](); t_end = time.time() + 5
while time.time() < t_end and len(dlg['S']['found']) < 4: root.update(); time.sleep(0.05)
check(any(r['new'] and r['mac'] == 'aa:bb:cc:99:99:99' for r in dlg['S']['found']) and any('NEW' in x for x in dlg['lb'].get(0, 'end')),
      'second scan marks the device that just appeared as NEW (finding your phone)')
idx = [i for i, r in enumerate(dlg['S']['found']) if r['name'] == 'iPhone'][0]
dlg['lb'].selection_set(idx); dlg['use'](); root.update(); time.sleep(0.3); root.update()
check(w2.prefs['phone_mac'] == '12:34:56:78:9a:bc' and w2.prefs['phone_name'] == 'iPhone', 'choosing the phone saves it')
t_end = time.time() + 3
while time.time() < t_end: root.update(); time.sleep(0.05)
check('Following iPhone' in dlg['ph_var'].get(), f"status line follows the phone ({dlg['ph_var'].get()[:60]})")
dlg['clear'](); check(w2.prefs['phone_mac'] == '', 'stop following clears it')
dlg['win'].destroy(); root.update()
print('RESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
