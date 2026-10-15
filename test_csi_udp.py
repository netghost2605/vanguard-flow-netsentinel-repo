#!/usr/bin/env python3
"""CSI over Wi-Fi: the app's UDP reader against a fake receiver board that behaves like the csi_recv firmware
(announces 'CSI_BOARD,...', waits for 'CSI_SUBSCRIBE', then streams one CSI line per datagram).
Run: python3.12 test_csi_udp.py"""
import importlib.util, os, socket, threading, time
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)

def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

class FakeBoard(threading.Thread):
    """announce -> subscribe -> stream, like main.c. Streams only while a subscription is < 8 s old."""
    def __init__(self, app_port, my_port, channel=6, cfg=11, hz=100, silent=False, beacon=True):
        super().__init__(daemon=True)
        self.app = ('127.0.0.1', app_port); self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', my_port)); self.sock.settimeout(0.05)
        self.stop_ev = threading.Event(); self.sub = None; self.sub_t = 0; self.sent = 0; self.subs = 0
        self.channel, self.cfg, self.hz, self.silent, self.beacon = channel, cfg, hz, silent, beacon
        self.sim = mod._NMCsiSim(seed=3)
    def run(self):
        t0 = time.time(); last_beacon = 0; n = 0
        self.sock.sendto(b'csi_recv ready: test board\n', self.app)
        while not self.stop_ev.is_set():
            now = time.time()
            if self.beacon and now - last_beacon >= 0.5:
                last_beacon = now
                self.sock.sendto(f'CSI_BOARD,csi_recv,127.0.0.1,{self.channel},-55,{self.cfg}\n'.encode(), self.app)
            try:
                d, a = self.sock.recvfrom(64)
                if d.startswith(b'CSI_SUBSCRIBE'):
                    self.sub, self.sub_t = a, now; self.subs += 1
            except socket.timeout:
                pass
            except OSError:
                pass
            if self.silent: continue
            due = int((time.time() - t0) * self.hz)
            while n < due:
                if self.sub and time.time() - self.sub_t < 8.0:
                    self.sock.sendto((self.sim.frame(n / self.hz) + '\n').encode(), self.sub); self.sent += 1
                n += 1
    def stop(self): self.stop_ev.set(); self.join(1.0); self.sock.close()

# 1. discovery + streaming
ap = free_port(); bp = free_port()
an = mod._NMCsiAnalyzer(); src = mod._NMCsiSource(an, udp_port=ap); src.start()
fb = FakeBoard(ap, bp); fb.start(); time.sleep(3.0)
check(src.board is not None and src.board['ip'] == '127.0.0.1' and src.board['ch'] == 6 and src.board['cfg'] == 11, f'udp: board announcement parsed ({src.board})')
check(fb.subs >= 1, f'udp: app answered the announcement with a subscription ({fb.subs} so far)')
check(an.frames >= 150 and src.bad == 0, f'udp: {an.frames} CSI frames arrived, {src.bad} damaged')
check(any('test board' in l for (_t, l) in src.log), 'udp: ordinary board messages are kept in the board log')
check(not any(l.startswith('CSI_BOARD') for (_t, l) in src.log), 'udp: announcements are not dumped into the board log')
check(src.hint() == '', f'udp: no hint while healthy ({src.hint()[:60]})')
check(len(src.copy_text(20).splitlines()) >= 150, 'udp: copy-raw works for Wi-Fi data too')
sent_before = fb.sent; src.stop(); time.sleep(0.6)
check(not src.alive() and src.sock is None, 'udp: reader thread stops and the socket is closed')

# 1b. announcements blocked (firewall / router drops broadcasts): the app's broadcast subscribe still gets a stream,
#     and it learns the board from the data itself
ap1 = free_port(); bp1 = free_port()
an1 = mod._NMCsiAnalyzer(); src1 = mod._NMCsiSource(an1, udp_port=ap1); src1.discover = [('127.0.0.1', bp1)]; src1.start()
fb1 = FakeBoard(ap1, bp1, beacon=False); fb1.start(); time.sleep(3.5)
check(fb1.subs >= 1 and an1.frames >= 100, f'udp: no announcements heard, broadcast subscribe still works ({an1.frames} frames, {fb1.subs} subscriptions)')
check(src1.board is not None and src1.board['ip'] == '127.0.0.1', 'udp: board learned from its data packets')
check(src1.hint() == '', f'udp: no false alarm without announcements ({src1.hint()[:50]})')
src1.stop(); fb1.stop(); time.sleep(0.4)

# 2. several datagrams worth of lines in one packet, CRLF, junk
ap2 = free_port(); an2 = mod._NMCsiAnalyzer(); src2 = mod._NMCsiSource(an2, udp_port=ap2); src2.start(); time.sleep(0.3)
cl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sim = mod._NMCsiSim(seed=4)
pkt = '\r\n'.join(sim.frame(i / 100.0) for i in range(3)) + '\r\nrandom junk\r\n'
cl.sendto(pkt.encode(), ('127.0.0.1', ap2)); cl.sendto(b'\xff\xfe not utf8\n', ('127.0.0.1', ap2)); time.sleep(0.5)
check(an2.frames == 3, f'udp: multi-line datagram with CRLF is split correctly ({an2.frames} frames)')
check(any('random junk' in l for (_t, l) in src2.log), 'udp: junk lines go to the log, not the analyzer')
src2.stop(); time.sleep(0.5)

# 3. port already in use -> clear error, no crash
ap3 = free_port(); hog = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'): hog.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
hog.bind(('', ap3))
src3 = mod._NMCsiSource(mod._NMCsiAnalyzer(), udp_port=ap3); src3.start(); time.sleep(1.6)
check('UDP port' in src3.error and str(ap3) in src3.error, f'udp: busy port reports a plain error ({src3.error[:70]})')
hog.close()

# 4. quick reconnect (stop then start the same port) works
ap4 = free_port(); s4a = mod._NMCsiSource(mod._NMCsiAnalyzer(), udp_port=ap4); s4a.start(); time.sleep(0.2); s4a.stop()
s4b = mod._NMCsiSource(mod._NMCsiAnalyzer(), udp_port=ap4); s4b.start(); time.sleep(0.8)
check(s4b.error == '' and s4b.alive(), 'udp: Disconnect then Connect straight away re-binds the port')
s4b.stop(); time.sleep(0.4)

# 5. hints, driven by a fake clock
clk = [1000.0]
ap5 = free_port(); s5 = mod._NMCsiSource(mod._NMCsiAnalyzer(), udp_port=ap5, clock=lambda: clk[0]); s5.t_start = 1000.0
clk[0] = 1002.0; check(s5.hint() == '', 'hint: quiet during the first 4 s')
clk[0] = 1010.0; h = s5.hint(); check('no receiver board has announced' in h and 'Firewall' in h and 'csi_config.h' in h, 'hint: nothing heard -> check power/flash/network/firewall')
s5.board = {'ip': '192.168.1.40', 'port': 4210, 'ch': 6, 'rssi': -60, 'cfg': 11, 't': 1009.0}
h = s5.hint(); check('192.168.1.40' in h and 'channel 6' in h and 'csi_send' in h, f'hint: board seen, no CSI -> says which channel the transmitter needs')
s5.t_last_csi = 1009.5; check(s5.hint() == '', 'hint: healthy once CSI is flowing')
clk[0] = 1020.0; check('stopped announcing' in s5.hint(), 'hint: board went quiet -> lost power / dropped off Wi-Fi')
s5.board['t'] = 1019.0; check('CSI stopped arriving' in s5.hint(), 'hint: board alive but CSI stopped -> transmitter')
s5.board['ch'] = 0; s5.board['cfg'] = 0; s5.t_last_csi = 0.0; s5.board['t'] = 1019.0; h = s5.hint(); check('same Wi-Fi channel as the receiver' in h, 'hint: board channel unknown -> says match the receiver')
s5.board['ch'] = 1; s5.board['auto'] = True; h = s5.hint()
check('by itself' in h and 'within about 5 seconds' in h and 'set to channel' not in h, 'hint: auto-channel receiver -> no channel to match, says the transmitter searches')
s5.board['auto'] = False; h = s5.hint(); check('channel 1' in h and 'Re-flash BOTH' in h, 'hint: older receiver firmware -> names the channel and says re-flash both once')
s5._board_line('CSI_BOARD,csi_recv,192.168.1.154,1,-60,11,auto', ('192.168.1.154', 4210), 1019.5)
check(s5.board['auto'] is True and s5.board['ch'] == 1 and s5.board['cfg'] == 11, 'announcement with ",auto" is recognised')
s5._board_line('CSI_BOARD,csi_recv,192.168.1.154,1,-60,11', ('192.168.1.154', 4210), 1019.5)
check(s5.board['auto'] is False, 'announcement from older firmware is recognised as such')
s5.error = 'boom'; check(s5.hint() == 'boom', 'hint: an error wins')

# 6. firmware is consistent with the app's expectations (static checks on the C source)
c = open(os.path.join(HERE, '..', 'esp32_csi', 'csi_recv', 'main', 'main.c')).read() if os.path.exists(os.path.join(HERE, '..', 'esp32_csi', 'csi_recv', 'main', 'main.c')) else ''
if c:
    check('CSI_BOARD,csi_recv,' in c and 'CSI_SUBSCRIBE' in c and 'SUB_TIMEOUT_MS     8000' in c, 'firmware: announce/subscribe strings and 8 s timeout match the app')
    check(',auto' in c and "'C', 'S', 'I', 'R'" in c and 'esp_now_add_peer' in c, 'firmware: receiver announces ",auto" and sends the CSIR beacon')
    cs = open(os.path.join(HERE, '..', 'esp32_csi', 'csi_send', 'main', 'main.c')).read()
    check("data[3] == 'R'" in cs and 'esp_now_register_recv_cb' in cs and 'peer.channel = 0' in cs and 'LOST_MS' in cs,
          'firmware: transmitter listens for the CSIR beacon, sends on the current channel and searches again when lost')
    check(str(mod._NM_CSI_UDP_PORT) in open(os.path.join(HERE, '..', 'esp32_csi', 'csi_recv', 'main', 'csi_config.h')).read(), 'firmware: default UDP port equals the app\'s')

print('\n%d failed' % len(fails) if fails else '\nALL OK')
raise SystemExit(1 if fails else 0)
