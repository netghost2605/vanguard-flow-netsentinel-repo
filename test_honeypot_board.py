#!/usr/bin/env python3
"""The receiver board's honeypot: the app parses a CSI_HONEYPOT report, records it like a PC honeypot hit
(history + live honeypot if open), and raises one away alert per source. Run: python3.12 test_honeypot_board.py"""
import importlib.util, os, sys, tempfile, time
os.environ['HOME'] = tempfile.mkdtemp()
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)

# ── the source parses CSI_HONEYPOT lines and calls back ──────────────────────
got = []
src = mod._NMCsiSource(mod._NMCsiAnalyzer(), udp_port=4210, on_honeypot=lambda d: got.append(d))
src._honeypot_line('CSI_HONEYPOT,192.168.1.66,23,tcp,726f6f740a', ('192.168.1.154', 4210), 1000.0)
check(len(got) == 1 and got[0]['ip'] == '192.168.1.66' and got[0]['port'] == 23 and got[0]['proto'] == 'tcp'
      and got[0]['first'] == b'root\n' and got[0]['board_ip'] == '192.168.1.154',
      'source parses CSI_HONEYPOT,<ip>,<port>,<proto>,<hex> and decodes the first bytes')
got.clear()
src._honeypot_line('CSI_HONEYPOT,not-an-ip,23,tcp,00', ('192.168.1.154', 4210), 1000.0)
check(not got, 'a bad source address is ignored')
src._honeypot_line('CSI_HONEYPOT,10.0.0.5,445,tcp,', ('192.168.1.154', 4210), 1000.0)
check(len(got) == 1 and got[0]['first'] == b'', 'a hit with no captured bytes still reports')
nohp = mod._NMCsiSource(mod._NMCsiAnalyzer(), udp_port=4210)       # no callback set
nohp._honeypot_line('CSI_HONEYPOT,10.0.0.9,23,tcp,00', ('192.168.1.154', 4210), 1000.0)
check(True, 'no callback: parsing a line does not raise')

# ── the watcher records a hit like the PC honeypot, and alerts ───────────────
class FakeDB:
    def __init__(self): self.hits = []
    def insert_honeypot_hit(self, rec): self.hits.append(rec)
alerts = []
db = FakeDB()
w = mod._NMWifiWatcher(None, scan_fn=lambda k: {'kind': k, 'ok': True, 'aps': [], 'raw': ''},
                       state_dir=tempfile.mkdtemp(), use_api=False, threads=False, db=db,
                       alert_fn=lambda t, m, s, image=None: alerts.append((t, m, s)), idle_fn=lambda: 9999)
mod._NM_HONEYPOT = None       # no PC honeypot running: the watcher persists straight to the DB
w._on_honeypot_hit({'ip': '192.168.1.66', 'port': 23, 'proto': 'tcp', 'first': b'root\r\n'})
check(len(db.hits) == 1 and db.hits[0]['ip'] == '192.168.1.66' and db.hits[0]['service'] == 'Telnet'
      and db.hits[0]['port'] == 23, 'no PC honeypot: the board hit is written to the honeypot history (named service)')
check(any(e['kind'] == 'HONEYPOT' and '192.168.1.66' in e['detail'] and 'Telnet' in e['detail'] for e in w.events),
      'a HONEYPOT event is recorded with the source and the decoy service')
time.sleep(0.3)
check(alerts and alerts[-1][0] == 'Honeypot: someone is probing your network' and '192.168.1.66' in alerts[-1][1],
      'a honeypot hit raises a phone alert')
n = len(alerts)
w._on_honeypot_hit({'ip': '192.168.1.66', 'port': 3389, 'proto': 'tcp', 'first': b''}); time.sleep(0.2)
check(len(alerts) == n, 'a second hit from the same source within 5 min does not re-alert (a sweep will not flood)')
w._on_honeypot_hit({'ip': '127.0.0.1', 'port': 23, 'proto': 'tcp', 'first': b''})
check(all('127.0.0.1' not in h['ip'] for h in db.hits), 'loopback is ignored (the board never probes itself)')

# ── when the PC honeypot IS running, the hit goes into it (live window + its own persistence) ──
class FakeHP:
    def __init__(self): self.rec = []
    def _record(self, ip, port, first, force=False, proto='tcp'): self.rec.append((ip, port, first, force, proto))
hp = FakeHP(); mod._NM_HONEYPOT = hp
db.hits.clear()
w._on_honeypot_hit({'ip': '192.168.1.80', 'port': 445, 'proto': 'tcp', 'first': b'\xffSMB'})
check(hp.rec and hp.rec[-1][0] == '192.168.1.80' and hp.rec[-1][3] is True and hp.rec[-1][4] == 'tcp'
      and not db.hits, 'with the honeypot open, the hit goes into it (which persists/dedups/updates the window), not a second DB write')
mod._NM_HONEYPOT = None

# ── the firmware shipped in the app actually contains the honeypot (and no OTA upload server) ──
rc = mod._nm_fw_files()['recv']['main/main.c']
check('honeypot_task' in rc and 'CSI_HONEYPOT' in rc and 'decoy' in rc, 'embedded receiver firmware contains the honeypot')
check('esp_ota_begin' not in rc and 'httpd_start' not in rc and '/ota' not in rc,
      'embedded firmware has no over-the-air firmware-upload server (never shipped)')
check('CONFIG_LWIP_MAX_SOCKETS=16' in mod._nm_fw_files()['recv']['sdkconfig.defaults'],
      'firmware raises the socket limit for the decoy listeners')
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
