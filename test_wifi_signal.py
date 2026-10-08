#!/usr/bin/env python3
"""
Wi-Fi Signal window: parsers (against real-format `netsh wlan` output, including
a localised/hidden-SSID case), the movement detector (quiet room vs a person
crossing the link), the survey smoother, and the REAL _nm_open_wifi() window
driven with a fake scanner under xvfb: live graph, networks tab with a new-AP
alarm, and a walk-around survey in 2D and 3D, saved to and reloaded from disk.

Run: xvfb-run -a python3.12 test_wifi_signal.py
"""
import importlib.util, os, sys, tempfile, time, random, json
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import numpy as np

IFACES = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201 160MHz
    GUID                   : 5a3b1c9e-aaaa-bbbb-cccc-0123456789ab
    Physical address       : 7c:b2:7d:11:22:33
    State                  : connected
    SSID                   : HomeNet
    BSSID                  : a4:2b:b0:aa:bb:cc
    Network type           : Infrastructure
    Radio type             : 802.11ax
    Authentication         : WPA2-Personal
    Cipher                 : CCMP
    Connection mode        : Auto Connect
    Channel                : 36
    Receive rate (Mbps)    : 866.7
    Transmit rate (Mbps)   : 780.5
    Signal                 : 94%
    Profile                : HomeNet
"""
IFACES_W11 = IFACES.replace('BSSID                  :', 'AP BSSID                :').replace('Channel                : 36', 'Band                   : 5 GHz\n    Channel                : 100')
IFACES_DOWN = IFACES.replace('connected', 'disconnected').replace('Signal                 : 94%\n', '')
NETS = """
Interface name : Wi-Fi
There are 4 networks currently visible.

SSID 1 : HomeNet
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
    BSSID 1                 : a4:2b:b0:aa:bb:cc
         Signal             : 94%
         Radio type         : 802.11ax
         Band               : 5 GHz
         Channel            : 36
    BSSID 2                 : a4:2b:b0:aa:bb:cd
         Signal             : 71%
         Radio type         : 802.11n
         Band               : 2.4 GHz
         Channel            : 6

SSID 2 : Neighbour-5G
    Network type            : Infrastructure
    Authentication          : WPA3-Personal
    Encryption              : CCMP
    BSSID 1                 : 10:20:30:40:50:60
         Signal             : 40%
         Radio type         : 802.11ac
         Channel            : 149

SSID 3 :
    Network type            : Infrastructure
    Authentication          : Open
    Encryption              : None
    BSSID 1                 : de:ad:be:ef:00:01
         Signal             : 22%
         Radio type         : 802.11n
         Channel            : 1
"""
LOCALISED = """
SSID 1 : Maison
    BSSID 1                 : aa:bb:cc:dd:ee:ff
         Signal             : 80 %
"""

failures = []
def check(c, m):
    if not c:
        failures.append(m); print('FAIL:', m)
    else:
        print('ok:  ', m)

# ── parsers ────────────────────────────────────────────────────────────────
ifs = mod._nm_wifi_parse_interfaces(IFACES)
lk = mod._nm_wifi_link_from_interfaces(ifs)
check(lk and lk['ssid'] == 'HomeNet' and lk['bssid'] == 'a4:2b:b0:aa:bb:cc', 'interfaces: SSID and BSSID (colons in value kept)')
check(lk['pct'] == 94 and abs(lk['dbm'] - (-53.0)) < 1e-9, 'interfaces: 94% -> -53 dBm')
check(lk['channel'] == 36 and lk['band'] == '5 GHz' and lk['rx'] == 866.7 and lk['tx'] == 780.5, 'interfaces: channel, band from channel, rates')
lk11 = mod._nm_wifi_link_from_interfaces(mod._nm_wifi_parse_interfaces(IFACES_W11))
check(lk11 and lk11['bssid'] == 'a4:2b:b0:aa:bb:cc' and lk11['channel'] == 100 and lk11['band'] == '5 GHz', "Windows 11 'AP BSSID' + 'Band' labels read as a link")
check(mod._nm_wifi_link_from_interfaces(mod._nm_wifi_parse_interfaces(IFACES.replace('BSSID                  : a4:2b:b0:aa:bb:cc\n', ''))) is not None, 'a link with no BSSID line at all is still a link')
check(mod._nm_wifi_link_from_interfaces(mod._nm_wifi_parse_interfaces(IFACES_DOWN)) is None, 'disconnected adapter -> no link')
check(mod._nm_wifi_link_from_interfaces(mod._nm_wifi_parse_interfaces('There is no wireless interface on the system.')) is None, 'no adapter -> no link')
aps = mod._nm_wifi_parse_networks(NETS)
check(len(aps) == 4, f'networks: 4 BSSIDs parsed ({len(aps)})')
check(aps[0]['ssid'] == 'HomeNet' and aps[1]['ssid'] == 'HomeNet' and aps[1]['band'] == '2.4 GHz' and aps[1]['channel'] == 6, 'networks: one SSID, two BSSIDs, bands')
check(aps[2]['band'] == '5 GHz' and aps[2]['auth'] == 'WPA3-Personal', 'networks: band from channel when no Band line; security carried')
check(aps[3]['ssid'] == '(hidden)' and aps[3]['auth'] == 'Open', 'networks: hidden SSID named')
loc = mod._nm_wifi_parse_networks(LOCALISED.replace('SSID 1', 'XXX 1').replace('BSSID 1', 'YYY 1'))
check(len(loc) == 1 and loc[0]['pct'] == 80, 'localised labels: falls back to MAC + NN%')

# ── movement detector ──────────────────────────────────────────────────────
random.seed(3)
m = mod._NMWifiMotion()
t0 = 1000.0; out = None; quiet_moving = False
for i in range(120):                       # 2 min of a still room: half-dB flicker
    v = -53.0 + random.choice([0, 0, 0, 0.5, -0.5])
    out = m.add(t0 + i, v); quiet_moving |= out['moving'] if out['ready'] else False
check(out['ready'] and not quiet_moving, 'detector: still room is calibrated and never flagged')
hit = False
for i in range(120, 135):                  # someone walks through the path
    v = -53.0 + random.choice([-6, -3, 2, -8, 0, -5, 1, -7])
    out = m.add(t0 + i, v); hit |= out['moving']
check(hit, 'detector: a person crossing the link is flagged as movement')
for i in range(135, 175):
    out = m.add(t0 + i, -53.0 + random.choice([0, 0, 0.5]))
check(not out['moving'], 'detector: back to quiet after they leave (hysteresis released)')

# ── survey smoother ────────────────────────────────────────────────────────
gx, gy, fld, cov = mod._nm_wifi_field([1, 2, 3], [1, 4, 7], [-40, -60, -80], 12, 8)
check(fld.shape == cov.shape and np.isfinite(fld).all() and fld.min() >= -80 - 1e-6 and fld.max() <= -40 + 1e-6, 'field: stays inside the sample range (no overshoot)')
check(cov[int(1 / 8 * fld.shape[0]), int(1 / 12 * fld.shape[1])] > 0.85 and cov[-1, -1] < 0.5, 'field: confident near samples, faint far away')

# ── the real window ────────────────────────────────────────────────────────
import tkinter as tk
class FM:
    theme_name = 'Ocean'
    @property
    def colors(self): return mod.THEMES['Ocean']
sd = tempfile.mkdtemp()
state = {'extra': False}
def fake_scan(kind):
    if kind == 'link':
        return {'kind': 'link', 't': time.time(), 'ok': True, 'error': '', 'raw': 'RAWLINK', 'adapters': 1, 'link': lk}
    ap = json.loads(json.dumps(aps))
    for a in ap: a['dbm'] = mod._nm_wifi_dbm(a['pct'])
    if state['extra']:
        ap.append({'ssid': 'HomeNet', 'bssid': '66:77:88:99:aa:bb', 'auth': 'WPA2-Personal', 'pct': 60, 'dbm': -70.0, 'channel': 11, 'band': '2.4 GHz', 'radio': '802.11n'})
    return {'kind': 'aps', 't': time.time(), 'ok': True, 'error': '', 'raw': 'RAWAPS', 'aps': ap}
root = tk.Tk(); root.withdraw()
win = mod._nm_open_wifi(FM(), scan_fn=fake_scan, state_dir=sd)
st = win._nm_state
deadline = time.time() + 6
while time.time() < deadline and not st['S']['aps']:
    root.update(); time.sleep(0.1)
check(st['S']['link'] and st['S']['link']['ssid'] == 'HomeNet', 'window: link arrives from the scanner thread')
check(len(st['S']['aps']) == 4 and len(st['net_tree'].get_children()) == 4, 'window: networks tab lists every access point')
kinds = [st['event_tree'].item(i, 'values')[1] for i in st['event_tree'].get_children()]
check('LEARNING' in kinds and 'NEW AP' not in kinds, 'first run: learning period announced, nothing flagged')
check(os.path.exists(os.path.join(sd, 'wifi_seen2.json')), 'known networks persisted to disk')
check(all('NEW' not in st['net_tree'].item(i, 'values')[8] for i in st['net_tree'].get_children()), 'learned networks are not labelled new')
# during learning a brand-new AP is absorbed silently
state['extra'] = True
for _ in range(4): st['on_aps'](fake_scan('aps'))
check(not any(st['event_tree'].item(i, 'values')[1] == 'NEW AP' for i in st['event_tree'].get_children()), 'an AP appearing during the learning window is absorbed silently')
# end learning, then a really new, strong AP appears
st['meta']['learn_until'] = 0; st['meta']['min_age'] = 0
def scan_extra(bssid, pct, name='HomeNet'):
    r = fake_scan('aps'); r['aps'].append({'ssid': name, 'bssid': bssid, 'auth': 'WPA2-Personal', 'pct': pct, 'dbm': mod._nm_wifi_dbm(pct), 'channel': 9, 'band': '2.4 GHz', 'radio': '802.11n'}); return r
for _ in range(2): st['on_aps'](scan_extra('02:00:00:00:00:01', 70))
check(not any(st['event_tree'].item(i, 'values')[1] == 'NEW AP' for i in st['event_tree'].get_children()), 'not flagged on first sightings (needs to persist for 3 scans)')
st['on_aps'](scan_extra('02:00:00:00:00:01', 70))
newev = [st['event_tree'].item(i, 'values') for i in st['event_tree'].get_children() if st['event_tree'].item(i, 'values')[1] == 'NEW AP']
check(len(newev) == 1 and 'same name as your network' in newev[0][2], 'a persistent strong new BSSID with your SSID raises one NEW AP alarm with the look-alike warning')
for _ in range(4): st['on_aps'](scan_extra('02:00:00:00:00:01', 70))
check(sum(1 for i in st['event_tree'].get_children() if st['event_tree'].item(i, 'values')[1] == 'NEW AP') == 1, 'the alarm fires once per access point, not every scan')
for _ in range(5): st['on_aps'](scan_extra('02:00:00:00:00:02', 20, 'FaintNeighbour'))
check(sum(1 for i in st['event_tree'].get_children() if st['event_tree'].item(i, 'values')[1] == 'NEW AP') == 1, 'a very faint new network (-90 dBm) does not alarm')
# synthetic minutes of link history incl. a movement burst, fed straight in
now = time.time(); random.seed(5)
st['link_hist'].clear(); st['motion'].stds.clear(); st['motion'].samples.clear()
for i in range(240):
    t = now - 240 + i
    v = -53.0 + (random.choice([-7, -3, 2, -8, 0, -5, 1, -6]) if 150 <= i < 175 else random.choice([0, 0, 0, 0.5, -0.5]))
    r = {'kind': 'link', 't': t, 'ok': True, 'raw': '', 'adapters': 1, 'link': dict(lk, dbm=v)}
    st['on_link'](r)
check(any(st['event_tree'].item(i, 'values')[1] == 'MOVEMENT' for i in st['event_tree'].get_children()), 'window: movement event logged')
check(len(st['S']['moves']) >= 1, 'window: movement span recorded for shading')
st['drain'](); root.update()
win._nm_fig_live = True
# survey: click-free, drive the same code path
for (x, y, v) in ((1, 1, -45), (5, 2, -55), (9, 1, -63), (2, 6, -58), (7, 6, -70), (10, 7, -78)):
    st['cursor']['x'], st['cursor']['y'] = x, y
    st['link_hist'].extend([(time.time(), v)] * 6)
    st['sample']()
check(len(st['survey']) == 6 and all(s['aps'] for s in st['survey']), 'survey: 6 samples stored with per-AP strengths')
saved = json.load(open(os.path.join(sd, 'wifi_survey.json')))
check(len(saved['samples']) == 6, 'survey persisted to disk')
SHOT = os.environ.get('WIFI_SHOTS')
if SHOT:
    st['drain'](); root.update()
    st['figs'][0].set_size_inches(11, 4.4); st['drain'](); st['figs'][0].savefig(os.path.join(SHOT, 'wifi_live.png'), dpi=90, facecolor=st['figs'][0].get_facecolor())
    st['figs'][1].set_size_inches(11, 3.2); st['figs'][1].savefig(os.path.join(SHOT, 'wifi_nets.png'), dpi=90, facecolor=st['figs'][1].get_facecolor())
    st['figs'][2].set_size_inches(8, 4.6); st['draw_map'](); st['figs'][2].savefig(os.path.join(SHOT, 'wifi_map2d.png'), dpi=90, facecolor=st['figs'][2].get_facecolor())
st['td'].set(True); st['draw_map'](); root.update()
if SHOT:
    st['figs'][2].savefig(os.path.join(SHOT, 'wifi_map3d.png'), dpi=90, facecolor=st['figs'][2].get_facecolor())
st['td'].set(False); st['draw_map'](); root.update()
win.destroy(); root.update()
win2 = mod._nm_open_wifi(FM(), scan_fn=fake_scan, state_dir=sd); root.update()
check(len(win2._nm_state['survey']) == 6 and len(win2._nm_state['seen']) >= 6, 'reopened window reloads survey and known networks')
win2.destroy()
print()
if failures:
    print('RESULT: FAIL', len(failures)); sys.exit(1)
print('RESULT: PASS')
