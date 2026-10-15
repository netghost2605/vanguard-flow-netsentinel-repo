#!/usr/bin/env python3
"""_NMCsiUdpBroker: one shared UDP socket per port fans each datagram out to every subscribed
_NMCsiSource, so the CSI tab, the background watcher and the Floor window can read the one Wi-Fi board
at the same time. Run: python3 test_csi_broker.py"""
import importlib.util, os, socket, sys, tempfile, time
os.environ['HOME'] = tempfile.mkdtemp()
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)

PORT = 14210
def csi_line(mac='1a:00:00:00:00:01'):
    vals = ','.join(str((i % 7) - 3) for i in range(128))
    return ('CSI_DATA,0,%s,-50,11,1,0,0,1,1,0,0,0,0,-95,0,1,0,100,0,51,0,128,1,"[%s]"' % (mac, vals))

# ── the broker is a per-port singleton ──────────────────────────────────────
b1 = mod._NMCsiUdpBroker.get(PORT)
b2 = mod._NMCsiUdpBroker.get(PORT)
check(b1 is b2, 'the broker is one shared instance per port')

# ── two independent sources subscribe to the same port and both receive the stream ──
a1, a2 = mod._NMCsiAnalyzer(), mod._NMCsiAnalyzer()
s1 = mod._NMCsiSource(a1, udp_port=PORT)
s2 = mod._NMCsiSource(a2, udp_port=PORT)
s1.start(); s2.start()
time.sleep(0.4)                                  # let both bind/subscribe
check(b1.sock is not None, 'the shared socket is bound once for all subscribers')
check(len(b1.subs) == 2, 'both sources are subscribed to the one broker')

# push some datagrams at the shared port; both analyzers should receive every frame
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for _ in range(20):
    tx.sendto(csi_line().encode(), ('127.0.0.1', PORT))
    time.sleep(0.01)
time.sleep(0.4)
check(a1.frames >= 15 and a2.frames >= 15,
      'both analyzers received the frames from the one socket (%d / %d)' % (a1.frames, a2.frames))

# a CSI_HONEYPOT line reaches a source that wants it, via the same shared socket
got = []
s3 = mod._NMCsiSource(mod._NMCsiAnalyzer(), udp_port=PORT, on_honeypot=lambda d: got.append(d))
s3.start(); time.sleep(0.3)
tx.sendto(b'CSI_HONEYPOT,192.168.1.9,23,tcp,726f6f74', ('127.0.0.1', PORT))
time.sleep(0.3)
check(len(got) == 1 and got[0]['ip'] == '192.168.1.9',
      'a honeypot line fans out to the subscriber that handles it')

# ── unsubscribing the last source closes the shared socket ──────────────────
s1.stop(); s2.stop(); s3.stop()
time.sleep(0.6)
check(not b1.subs, 'all sources unsubscribed')
check(b1.sock is None, 'the shared socket is closed once the last subscriber leaves')

# ── the port is now free again (no leaked exclusive bind) ───────────────────
try:
    chk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        chk.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    chk.bind(('', PORT)); chk.close()
    check(True, 'the port can be re-bound after the broker releases it')
except Exception as e:
    check(False, 'the port is still held after the broker should have released it: %s' % e)

# ── the app wires the Floor window to the broker (no csi_pause fight) ────────
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check('_NMCsiUdpBroker.get(' in src and 'def _udp_consume' in src, 'sources route UDP through the broker')
check('no need to pause the background watcher' in src, 'the Floor window no longer pauses Keep-watching')

print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
