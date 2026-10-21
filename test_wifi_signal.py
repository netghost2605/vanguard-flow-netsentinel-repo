#!/usr/bin/env python3
"""
Wi-Fi Signal: parsers (real-format netsh output), the movement detector, the
Windows-API helper protocol (fake helper process), per-AP tracker, rogue findings,
health score, history database, the watcher (learning, new-AP, away alerts, API
mode and fallback), dead spots, and the REAL _nm_open_wifi() window under xvfb.

Run: xvfb-run -a python3.12 test_wifi_signal.py   (WIFI_SHOTS=<dir> saves screenshots)
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

# ── survey smoother + dead spots ───────────────────────────────────────────
gx, gy, fld, cov = mod._nm_wifi_field([1, 2, 3], [1, 4, 7], [-40, -60, -80], 12, 8)
check(fld.shape == cov.shape and np.isfinite(fld).all() and fld.min() >= -80 - 1e-6 and fld.max() <= -40 + 1e-6, 'field: stays inside the sample range (no overshoot)')
check(cov[int(1 / 8 * fld.shape[0]), int(1 / 12 * fld.shape[1])] > 0.85 and cov[-1, -1] < 0.5, 'field: confident near samples, faint far away')
xs = [1, 3, 5, 7, 9, 11, 1, 3, 5, 7, 9, 11, 2, 6, 10]
ys = [1, 1, 1, 1, 1, 1, 4, 4, 4, 4, 4, 4, 7, 7, 7]
vs = [-40, -45, -50, -58, -66, -74, -42, -48, -55, -64, -72, -80, -46, -62, -82]
gx, gy, fld, cov = mod._nm_wifi_field(xs, ys, vs, 12, 8)
ds = mod._nm_wifi_dead_spots(gx, gy, fld, cov, thr=-75.0, router=(1.0, 1.0))
check(len(ds['regions']) >= 1 and ds['regions'][0]['cx'] > 8, f"dead spots: weak far side found ({len(ds['regions'])} region(s))")
check(ds['suggest'] is not None and 1.0 < ds['suggest'][0] < ds['regions'][0]['cx'], 'dead spots: suggested node sits between router and the dead area')
ds2 = mod._nm_wifi_dead_spots(gx, gy, fld, cov, thr=-95.0)
check(ds2['regions'] == [] and ds2['suggest'] is None, 'dead spots: none reported when everything is above the threshold')

# ── channel / frequency helpers ────────────────────────────────────────────
check(mod._nm_wifi_freq_to_channel(2437000) == (6, '2.4 GHz') and mod._nm_wifi_freq_to_channel(5180000) == (36, '5 GHz')
      and mod._nm_wifi_freq_to_channel(5955000) == (1, '6 GHz') and mod._nm_wifi_freq_to_channel(2484000)[0] == 14, 'WLAN API centre frequency -> channel and band')
api = mod._nm_wifi_api_aps([{'s': 'HomeNet', 'b': 'a4:2b:b0:aa:bb:cc', 'r': -53, 'q': 90, 'f': 5180000},
                            {'s': '', 'b': '02:11:22:33:44:55', 'r': -80, 'q': 40, 'f': 2412000},
                            {'s': 'x', 'b': '', 'r': -1, 'f': 0}],
                           {'02:11:22:33:44:55': {'auth': 'Open', 'ssid': 'Cafe', 'radio': '802.11n'}})
check(len(api) == 2 and api[0]['channel'] == 36 and api[1]['ssid'] == 'Cafe' and api[1]['auth'] == 'Open' and api[0]['pct'] == 94, 'API APs: converted, hidden name filled from netsh metadata, empty BSSID dropped')

# ── helper protocol with a fake helper process ─────────────────────────────
import textwrap
fake_helper = os.path.join(tempfile.mkdtemp(), 'fake_helper.py')
open(fake_helper, 'w').write(textwrap.dedent('''
    import sys, time
    print('garbage line that is not json'); sys.stdout.flush()
    print('{"k":"hello","ifaces":1}'); sys.stdout.flush()
    for i in range(30):
        print('{"k":"rssi","i":0,"v":%d}' % (-52 - (i % 2))); sys.stdout.flush()
        if i == 5:
            print('{"k":"bss","i":0,"aps":[{"s":"HomeNet","b":"a4:2b:b0:aa:bb:cc","r":-53,"q":90,"f":5180000}]}'); sys.stdout.flush()
        time.sleep(0.02)
    print('{"k":"err","msg":"BssList 5"}'); sys.stdout.flush()
    time.sleep(0.3)
'''))
got = []
src = mod._NMWifiApiSource(got.append, scan_s=12, cmd=[sys.executable, fake_helper])
check(src.start(), 'helper: process starts')
t_end = time.time() + 8
while time.time() < t_end and not any(m.get('k') == 'err' for m in got):
    time.sleep(0.05)
kinds = [m.get('k') for m in got]
check(kinds.count('rssi') == 30 and 'hello' in kinds and 'bss' in kinds and 'err' in kinds, f'helper: JSON lines parsed, junk ignored ({kinds.count("rssi")} rssi)')
src.stop()
bad = mod._NMWifiApiSource(lambda m: None, cmd=['/definitely/not/a/program'])
check(bad.start() is False and bad.error, 'helper: failure to start is reported, not raised')

# ── per-AP tracker ─────────────────────────────────────────────────────────
random.seed(11)
trk = mod._NMWifiApTracker()
for i in range(120):
    t = 5000 + i * 10
    trk.add(t, 'aa:aa:aa:aa:aa:01', -60 + random.choice([0, 1, -1, 0]))
    wild = i >= 112
    trk.add(t, 'aa:aa:aa:aa:aa:02', -65 + (random.choice([-9, 7, -8, 10, -6]) if wild else random.choice([0, 1, -1])))
s1, s2 = trk.state['aa:aa:aa:aa:aa:01'], trk.state['aa:aa:aa:aa:aa:02']
check(s1['ready'] and not s1['disturbed'], 'tracker: a steady path is not disturbed')
check(s2['ready'] and s2['disturbed'] and s2['swing'] >= 6, 'tracker: a path that starts swinging is flagged, the steady one is not')

# ── findings, vendor, health, advice ───────────────────────────────────────
check(mod._nm_wifi_vendor('b8:27:eb:11:22:33') == 'Raspberry Pi' and mod._nm_wifi_vendor('ba:27:eb:11:22:33') == 'Raspberry Pi', 'vendor: locally-administered bit is cleared before the lookup')
check(mod._nm_wifi_device_key('a6:2b:b0:aa:bb:cc') == mod._nm_wifi_device_key('a4:2b:b0:aa:bb:ee'), 'device key: multi-SSID BSSIDs map to the same box')
mylink = {'ssid': 'HomeNet', 'bssid': '00:1a:11:aa:bb:cc', 'auth': 'WPA2-Personal', 'dbm': -52.0, 'channel': 36, 'band': '5 GHz', 'rx': 866.0}
def ap(b, ssid='HomeNet', auth='WPA2-Personal', dbm=-60.0, ch=1, band='2.4 GHz'):
    return {'ssid': ssid, 'bssid': b, 'auth': auth, 'dbm': dbm, 'channel': ch, 'band': band}
fl = mod._nm_wifi_findings([ap('00:1a:11:aa:bb:cc'), ap('de:ad:be:ef:00:01', auth='Open')], mylink)
check(len(fl) == 1 and fl[0]['sev'] == 'high' and fl[0]['kind'] == 'open-lookalike', 'findings: open copy of your network name is HIGH')
fl = mod._nm_wifi_findings([ap('b8:27:eb:11:22:33')], mylink)
check(len(fl) == 1 and fl[0]['kind'] == 'other-maker' and 'Raspberry Pi' in fl[0]['text'], 'findings: same name, different maker -> warning naming the maker')
fl = mod._nm_wifi_findings([ap('b8:27:eb:11:22:33')], mylink, learned={'b8:27:eb:11:22:33'})
check(fl == [], 'findings: a node learned as normal is not re-flagged')
fl = mod._nm_wifi_findings([ap('00:1a:11:aa:bb:ee', auth='WPA-Personal')], dict(mylink, auth='WPA3-Personal'))
check(len(fl) == 1 and fl[0]['sev'] == 'info', 'findings: weaker security from the same maker is info only')
check(mod._nm_wifi_findings([ap('b8:27:eb:11:22:33')], None) == [], 'findings: nothing when not connected')
h = mod._nm_wifi_health(mylink, [ap('00:1a:11:aa:bb:cc', ch=36, band='5 GHz')], 0.5, [])
check(h and h['score'] >= 80 and h['grade'] in 'AB' and abs(sum(f[1] for f in h['factors']) - h['score']) <= 1, f"health: strong 5 GHz WPA2 link scores well ({h['score']})")
weak = dict(mylink, dbm=-84.0, band='2.4 GHz', channel=6, auth='Open', rx=20.0)
crowd = [ap('10:00:00:00:00:%02x' % i, ssid='N%d' % i, ch=6, dbm=-55.0) for i in range(8)]
h2 = mod._nm_wifi_health(weak, crowd, 2.5, [{'sev': 'high'}])
check(h2['score'] < 40 and h2['score'] < h['score'], f"health: weak, open, crowded link with a rogue scores badly ({h2['score']})")
check(mod._nm_wifi_health(None, [], None, []) is None, 'health: none when not connected')
adv = mod._nm_wifi_channel_advice(crowd + [ap('aa:aa:aa:aa:aa:aa', ch=1, dbm=-90.0)], dict(weak))
check(any('2.4 GHz' in l and ('channel 1' in l or 'channel 11' in l) for l in adv), f'advice: moves you off a crowded channel 6 -> {adv}')

# ── history database ───────────────────────────────────────────────────────
from datetime import datetime, timedelta
db = mod.SpeedDB(os.path.join(tempfile.mkdtemp(), 'wifi_test.db'))
check(mod._nm_wifi_db_init(db), 'history: tables created')
now_dt = datetime.now().replace(second=0, microsecond=0)
for d in range(3):
    base = now_dt - timedelta(days=d)
    for mi in range(60):
        t = base.replace(hour=14, minute=mi)
        mod._nm_wifi_db_put_minute(db, t.strftime('%Y-%m-%dT%H:%M'), 1.0 if mi < 15 else 0.0, 2.0, -54.0, 60)
grid, counts, last24 = mod._nm_wifi_activity_grid(db, 30)
cell = grid[now_dt.weekday(), 14]
check(abs(cell - 25.0) < 1e-6 and counts[now_dt.weekday(), 14] == 60, f'history: 15 of 60 minutes moving -> 25% in that weekday/hour cell ({cell})')
check(np.isnan(grid[now_dt.weekday(), 3]) and len(last24) == 24, 'history: unrecorded hours stay empty, last-24h strip has 24 slots')
mod._nm_wifi_db_put_event(db, '2026-01-01T10:00:00', 'MOVEMENT', 'x')
check(mod._nm_wifi_db_events(db, 5)[0][1] == 'MOVEMENT', 'history: events round-trip')

# ── the watcher (no window, no threads: driven directly) ───────────────────
class FM:
    theme_name = 'Ocean'
    config = {}
    @property
    def colors(self): return mod.THEMES['Ocean']
def mk(sd, **kw):
    alerts = []
    kw.setdefault('use_api', False)
    w = mod._NMWifiWatcher(FM(), scan_fn=lambda k: {'kind': k, 'ok': True, 'aps': [], 'raw': ''}, state_dir=sd, db=db,
                           threads=False, alert_fn=lambda t, m, s: alerts.append((t, m, s)), **kw)
    return w, alerts
def lkres(dbm, t=None):
    return {'kind': 'link', 't': t or time.time(), 'ok': True, 'raw': 'RAWLINK', 'adapters': 1, 'link': dict(lk, dbm=dbm)}
def evk(w): return [e['kind'] for e in w.events]
sd = tempfile.mkdtemp()
w, alerts = mk(sd)
w.ingest_aps({'t': time.time(), 'ok': True, 'aps': json.loads(json.dumps(aps)), 'raw': 'RAWAPS'})
for a in w.aps: pass
check(len(w.aps) == 4 and 'LEARNING' in evk(w) and 'NEW AP' not in evk(w), 'watcher: first run learns, flags nothing')
check(os.path.exists(os.path.join(sd, 'wifi_seen2.json')), 'watcher: known networks persisted')
def with_extra(bssid, dbm, ssid='HomeNet', auth='WPA2-Personal'):
    out = json.loads(json.dumps(aps))
    for a in out: a['dbm'] = mod._nm_wifi_dbm(a['pct'])
    out.append({'ssid': ssid, 'bssid': bssid, 'auth': auth, 'pct': 70, 'dbm': dbm, 'channel': 9, 'band': '2.4 GHz', 'radio': '802.11n'})
    return {'t': time.time(), 'ok': True, 'aps': out, 'raw': ''}
w._process_link(time.time(), dict(lk))     # so the watcher knows "my" SSID
for _ in range(4): w.ingest_aps(with_extra('02:00:00:00:00:01', -60.0))
check('NEW AP' not in evk(w), 'watcher: an AP appearing during the learning window is absorbed')
w.meta['learn_until'] = 0; w.meta['min_age'] = 0
for _ in range(2): w.ingest_aps(with_extra('02:00:00:00:00:09', -60.0))
check('NEW AP' not in evk(w), 'watcher: needs 3 sightings before an alarm')
w.ingest_aps(with_extra('02:00:00:00:00:09', -60.0))
time.sleep(0.2)
newev = [e for e in w.events if e['kind'] == 'NEW AP']
check(len(newev) == 1 and 'same name as your network' in newev[0]['detail'], 'watcher: persistent strong look-alike raises one NEW AP event')
check(len(alerts) >= 1 and alerts[0][0].startswith('Wi-Fi'), 'watcher: look-alike pushes an alert even when you are not away')
n_ev = len(newev)
for _ in range(4): w.ingest_aps(with_extra('02:00:00:00:00:09', -60.0))
check(sum(1 for e in w.events if e['kind'] == 'NEW AP') == n_ev, 'watcher: one alarm per access point')
for _ in range(5): w.ingest_aps(with_extra('02:00:00:00:00:77', -92.0, 'Faint'))
check(not any('02:00:00:00:00:77' in e['detail'] for e in w.events), 'watcher: a very faint network does not alarm')
w.ingest_aps(with_extra('de:ad:be:ef:00:05', -58.0, auth='Open'))
time.sleep(0.2)
check('ROGUE' in evk(w) and any(f['sev'] == 'high' for f in w.findings), 'watcher: open look-alike -> ROGUE event + high finding')
check(w.health and w.health['score'] is not None and w.advice, 'watcher: health score and channel advice are produced')
snap = w.snapshot()
json.dumps(snap)
check(snap['link'] and len(snap['aps']) >= 5 and snap['health'] and 'findings' in snap and snap['mode'] == 'netsh', 'watcher: snapshot is compact JSON with link, APs, health, findings')
check(any(a['maker'] != '' or a['dev'] for a in snap['aps']), 'watcher: APs carry maker / device key')
# movement + away alerts
random.seed(5)
alerts.clear()
w2, alerts2 = mk(tempfile.mkdtemp())
t0 = time.time() - 400
for i in range(300):
    w2._process_link(t0 + i, dict(lk, dbm=-53.0 + random.choice([0, 0, 0, 0.5, -0.5])))
check('MOVEMENT' not in evk(w2), 'watcher: a still room raises no movement')
for i in range(300, 320):
    w2._process_link(t0 + i, dict(lk, dbm=-53.0 + random.choice([-7, -3, 2, -8, 0, -5, 1, -6])))
time.sleep(0.2)
check('MOVEMENT' in evk(w2) and alerts2 == [], 'watcher: movement while you are HERE is logged but silent')
for i in range(320, 360):
    w2._process_link(t0 + i, dict(lk, dbm=-53.0 + random.choice([0, 0, 0.5])))
w2.set_pref('away', True)
check(not w2.is_away(), 'watcher: away ticked but you are at the PC -> not away')
w2.idle_fn = lambda: 1000.0          # PC left unused
check(w2.is_away(), 'watcher: away toggle')
for i in range(360, 380):
    w2._process_link(t0 + i, dict(lk, dbm=-53.0 + random.choice([-7, -3, 2, -8, 0, -5, 1, -6])))
time.sleep(0.3)
check(len(alerts2) == 1 and 'away' in alerts2[0][0].lower(), f'watcher: movement while AWAY alerts ({len(alerts2)})')
w3, _a3 = mk(tempfile.mkdtemp(), idle_fn=lambda: 1000.0)
check(not w3.is_away(), 'watcher: auto-away is off by default')
w3.set_pref('auto_away_min', 10)
check(w3.is_away(), 'watcher: auto-away after 10 min idle')
w3.idle_fn = lambda: 30.0
check(not w3.is_away(), 'watcher: not away when recently active')
w2.stop()
grid2, _c, _l = mod._nm_wifi_activity_grid(db, 1)
check(not np.isnan(grid2).all(), 'watcher: finished minutes are written to the history database')
# prefs persist
w4, _a4 = mk(sd); 
w.set_pref('background', True)
w5, _a5 = mk(sd)
check(w5.prefs['background'] is True and w5.meta['learn_until'] == 0, 'watcher: prefs and learned state survive a restart')

# API mode and fallback
class FakeApi:
    last = None
    def __init__(self, on_msg, scan_s=12):
        self.on_msg, self.scan_s, self.error = on_msg, scan_s, ''
        FakeApi.last = self
    def start(self): return True
    def stop(self): pass
wa, _aa = mk(tempfile.mkdtemp(), use_api=True, api_cls=FakeApi)
wa.start()
check(wa.mode == 'starting', 'API mode: starts in "starting" until the helper speaks')
wa._remember_link({'ok': True, 'link': lk, 'raw': '', 'adapters': 1})
FakeApi.last.on_msg({'k': 'rssi', 'i': 0, 'v': -51})
check(wa.mode == 'api' and wa.link and wa.link['dbm'] == -51.0 and wa.link['ssid'] == 'HomeNet' and wa.motion.min_thr == 1.2, 'API mode: first reading switches over, keeps netsh link details, raises motion floor')
FakeApi.last.on_msg({'k': 'rssi', 'i': 0, 'v': 12})
check(wa.link['dbm'] == -51.0, 'API mode: nonsense RSSI ignored')
FakeApi.last.on_msg({'k': 'bss', 'i': 0, 'aps': [{'s': 'HomeNet', 'b': 'a4:2b:b0:aa:bb:cc', 'r': -50, 'q': 90, 'f': 5180000}]})
check(len(wa.aps) == 1 and wa.aps[0]['dbm'] == -50.0, 'API mode: BSS lists feed the AP view')
wa.stop()
wf, _af = mk(tempfile.mkdtemp(), use_api=True, api_cls=FakeApi)
wf.start(); wf._t0 -= 30
wf._link_loop_once = None
wf._fallback('no readings')
check(wf.mode == 'netsh' and any('netsh' in e['detail'] for e in wf.events), 'API mode: falls back to netsh with an explanation')
wf.stop()

# ── the real window ────────────────────────────────────────────────────────
import tkinter as tk
root = tk.Tk(); root.withdraw()
sd2 = tempfile.mkdtemp()
ww, aw = mk(sd2)
win = mod._nm_open_wifi(FM(), watcher=ww, state_dir=sd2)
st = win._nm_state
now = time.time(); random.seed(2)
ww.meta['learn_until'] = 0
for i in range(240):
    t = now - 240 + i
    v = -53.0 + (random.choice([-7, -3, 2, -8, 0, -5, 1, -6]) if 150 <= i < 175 else random.choice([0, 0, 0, 0.5, -0.5]))
    ww._process_link(t, dict(lk, dbm=v))
ww.ingest_aps({'t': time.time(), 'ok': True, 'aps': json.loads(json.dumps(aps)), 'raw': 'RAWAPS'})
for a in ww.aps: a.setdefault('disturbed', False)
st['drain'](); root.update()
check(len(st['net_tree'].get_children()) == 4, 'window: networks tab lists every access point')
check(any(st['event_tree'].item(i, 'values')[1] == 'MOVEMENT' for i in st['event_tree'].get_children()), 'window: movement event shown')
st['nb'].select(2); root.update(); st['draw_activity']()
st['nb'].select(1); root.update(); st['draw_nets']()
st['nb'].select(0); root.update(); st['draw_live']()
for (x, y, v) in ((1, 1, -45), (5, 2, -55), (9, 1, -63), (2, 6, -58), (7, 6, -70), (10, 7, -82), (11, 3, -80), (10, 5, -84)):
    st['cursor']['x'], st['cursor']['y'] = x, y
    ww.link_hist.extend([(time.time(), v)] * 6)
    st['sample']()
check(len(st['survey']) == 8 and all(s['aps'] for s in st['survey']), 'survey: samples stored with per-AP strengths')
saved = json.load(open(os.path.join(sd2, 'wifi_survey.json')))
check(len(saved['samples']) == 8, 'survey persisted to disk')
st['plan']['routers']['0'] = [1.0, 1.0]
st['nb'].select(3); root.update(); st['draw_map']()
SHOT = os.environ.get('WIFI_SHOTS')
def shot(fig, name, w_=11, h_=4.4):
    if SHOT:
        fig.set_size_inches(w_, h_); fig.savefig(os.path.join(SHOT, name), dpi=90, facecolor=fig.get_facecolor())
if SHOT:
    shot(st['figs'][0], 'wifi_live.png'); shot(st['figs'][1], 'wifi_nets.png', 11, 3.2)
    shot(st['figs'][2], 'wifi_activity.png', 11, 4.4); shot(st['figs'][3], 'wifi_map2d.png', 8, 4.6)
st['td'].set(True); st['draw_map'](); root.update()
if SHOT: shot(st['figs'][3], 'wifi_map3d.png', 8, 4.6)
st['td'].set(False)
for choice in list(st['what_cb']['values']) if hasattr(st['what_cb'], '__getitem__') else []:
    st['what'].set(choice); st['draw_map']()
root.update()
check(True, 'window: every map layer (all bands, per-AP, band comparison) draws without error')
win.destroy(); root.update()
ww2, _x = mk(sd2)
win2 = mod._nm_open_wifi(FM(), watcher=ww2, state_dir=sd2); root.update()
check(len(win2._nm_state['survey']) == 8, 'reopened window reloads the survey')
win2.destroy()
print()
if failures:
    print('RESULT: FAIL', len(failures)); sys.exit(1)
print('RESULT: PASS')
