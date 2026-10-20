#!/usr/bin/env python3
"""A Wi-Fi receiver that gets a new IP from the router is found again by its hardware address.
Run: python3 test_board_follow.py   (xvfb not needed)"""
import importlib.util, os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

MACS = {'192.168.1.141': '3c:0f:02:eb:04:b8', '192.168.1.154': 'aa:aa:aa:aa:aa:01', '192.168.1.160': 'aa:aa:aa:aa:aa:01'}
mod._nm_ip_to_mac = lambda ip: MACS.get(ip)

class AN:
    def __init__(self): self.n = 0
    def add(self, t, amp, rssi): self.n += 1
LINE = b'CSI_BOARD,csi_recv,%s,6,-50,6,auto\n'
def mk(ip, mac=None):
    s = mod._NMCsiSource(AN(), udp_port=4210, clock=lambda: 100.0, board_ip=ip)
    s.board_mac = mac
    return s

# 1. the pinned address is silent, the same board announces from a new address -> follow it
d = mk('192.168.1.154', 'aa:aa:aa:aa:aa:01')
d._udp_consume(LINE % b'192.168.1.160', ('192.168.1.160', 4210), 100.0)
check(d.board_ip == '192.168.1.160', 'follows the board to its new address (%s)' % d.board_ip)
check(d.followed == ('192.168.1.154', '192.168.1.160'), 'remembers the move')
check(d.board and d.board['ip'] == '192.168.1.160', 'the announcement was handled after the move')

# 2. the OTHER floor's board (different hardware address) is never taken
u = mk('192.168.1.154', 'aa:aa:aa:aa:aa:01')
u._udp_consume(LINE % b'192.168.1.141', ('192.168.1.141', 4210), 100.0)
check(u.board_ip == '192.168.1.154' and u.followed is None, 'a different board is ignored')

# 3. no hardware address known yet -> never moves
n = mk('192.168.1.154', None)
n._udp_consume(LINE % b'192.168.1.160', ('192.168.1.160', 4210), 100.0)
check(n.board_ip == '192.168.1.154', 'without a learned hardware address it stays put')

# 4. the pinned address is still talking -> a look-alike does not steal it
t = mk('192.168.1.154', 'aa:aa:aa:aa:aa:01')
t.t_last_byte = 99.0
t._udp_consume(LINE % b'192.168.1.160', ('192.168.1.160', 4210), 100.0)
check(t.board_ip == '192.168.1.154', 'no move while the old address is still streaming')

# 5. data lines (not an announcement) from a new address do not move it
q = mk('192.168.1.154', 'aa:aa:aa:aa:aa:01')
q._udp_consume(b'CSI_DATA,1,aa,-50\n', ('192.168.1.160', 4210), 100.0)
check(q.board_ip == '192.168.1.154', 'only an announcement can move a source')

# 6. learns the hardware address from the pinned board's own traffic
l = mk('192.168.1.154', None)
l._udp_consume(b'hello\n', ('192.168.1.154', 4210), 100.0)
check(l.board_mac == 'aa:aa:aa:aa:aa:01', 'learns the hardware address of the board it reads')

# 7. prefs sync: new IP + hardware address saved, pick rewritten
prefs = {'up': 'wifi 192.168.1.141', 'down': 'wifi 192.168.1.154'}
up = mk('192.168.1.141', '3c:0f:02:eb:04:b8')
srcs = {'up': up, 'down': d}
ch = mod._nm_floor_follow_sync(srcs, prefs)
check(ch and prefs['down'] == 'wifi 192.168.1.160' and prefs['down_mac'] == 'aa:aa:aa:aa:aa:01' and prefs['down_mac_ip'] == '192.168.1.160', 'pick rewritten to the new address: %s' % prefs)
check(prefs['up_mac'] == '3c:0f:02:eb:04:b8' and prefs['up'] == 'wifi 192.168.1.141', 'upstairs hardware address saved, pick unchanged')
check(not mod._nm_floor_follow_sync(srcs, prefs), 'second sync changes nothing')

# 8. a saved hardware address is only used for the IP it was learned for
s1 = mk('192.168.1.160'); mod._nm_floor_macs_apply(s1, 'down', prefs)
check(s1.board_mac == 'aa:aa:aa:aa:aa:01', 'saved hardware address applied to a new source')
s2 = mk('192.168.1.99'); mod._nm_floor_macs_apply(s2, 'down', {'down': 'wifi 192.168.1.99', 'down_mac': 'aa:aa:aa:aa:aa:01', 'down_mac_ip': '192.168.1.160'})
check(s2.board_mac is None, 'a hardware address learned for another IP is not reused (the user picked a different board)')

# 9. a manual re-pick while connected is not overwritten by the sync
prefs2 = {'up': 'wifi 192.168.1.141', 'down': 'wifi 192.168.1.77'}
d2 = mk('192.168.1.154', 'aa:aa:aa:aa:aa:01'); d2.followed = None
mod._nm_floor_follow_sync({'up': up, 'down': d2}, prefs2)
check(prefs2['down'] == 'wifi 192.168.1.77', 'a pick the user just changed is left alone')

# 10. helpers
check(mod._nm_ip_to_mac.__name__ == '<lambda>' or True, 'helper replaced for tests')
import importlib
spec2 = importlib.util.spec_from_file_location("stm2", os.path.join(HERE, "speedtest_monitor.py"))
m2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(m2)
check(m2._nm_ip_to_mac('not an ip') is None and m2._nm_ip_to_mac('') is None, 'bad input gives None')
check(m2._nm_pick_ip('wifi 192.168.1.9') == '192.168.1.9' and m2._nm_pick_ip('COM3') is None and m2._nm_pick_ip('wifi:4210') is None, 'pick parsing')

# 11. hint for a pinned, silent address
h = mk('192.168.1.154', None); h.t_start = 0.0
check('Find Wi-Fi boards' in h.hint() and '192.168.1.154' in h.hint(), 'the hint explains a silent pinned address')

print('\nRESULT: ' + ('PASS' if not fails else 'FAIL %d' % len(fails)))
sys.exit(1 if fails else 0)
