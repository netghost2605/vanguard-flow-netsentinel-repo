#!/usr/bin/env python3
"""The Devices map draws its connection lines from the router: the router must be found even with a VPN connected.
Run: python3 test_lan_gateway.py   (xvfb not needed)"""
import importlib.util, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

IPC = """
Windows IP Configuration

Unknown adapter NordLynx:

   Connection-specific DNS Suffix  . :
   IPv4 Address. . . . . . . . . . . : 10.5.0.2
   Subnet Mask . . . . . . . . . . . : 255.255.255.255
   Default Gateway . . . . . . . . . : 10.5.0.1

Ethernet adapter Ethernet:

   Connection-specific DNS Suffix  . : lan
   Link-local IPv6 Address . . . . . : fe80::1234%12
   IPv4 Address. . . . . . . . . . . : 192.168.1.164
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : fe80::aaaa:bbbb%12
                                       192.168.1.254

Wireless LAN adapter WiFi:

   IPv4 Address. . . . . . . . . . . : 192.168.1.122
   Default Gateway . . . . . . . . . : 192.168.1.254

Ethernet adapter VMware Network Adapter VMnet8:

   IPv4 Address. . . . . . . . . . . : 192.168.160.1
   Default Gateway . . . . . . . . . :
"""
P = mod._nm_parse_lan_gateway
check(P(IPC, True) == '192.168.1.254', 'ipconfig with NordLynx listed first: the router is found, not the VPN (%r)' % P(IPC, True))
check(mod._nm_default_gateway.__name__ and True, 'plain default-gateway helper still exists')
ONLY_VPN = "Unknown adapter NordLynx:\n\n   Default Gateway . . . . . . . . . : 10.5.0.1\n"
check(P(ONLY_VPN, True) == '', 'only a VPN gateway: nothing claimed as the router')
PLAIN = "Ethernet adapter Ethernet:\n\n   Default Gateway . . . . . . . . . : 192.168.0.1\n"
check(P(PLAIN, True) == '192.168.0.1', 'no VPN: the ordinary gateway')
ROUTE = "default via 10.5.0.1 dev nordlynx proto static metric 50\ndefault via 192.168.1.254 dev eth0 proto dhcp metric 100\n"
check(P(ROUTE, False) == '192.168.1.254', 'Linux: skips the VPN default route')
check(P('', True) == '' and P('garbage', False) == '', 'empty or odd output is harmless')

# the map really draws a line from the router to every online device when the router is known
import matplotlib; matplotlib.use('Agg')
from matplotlib.figure import Figure
devs = []
def dv(ip, grp, gw=False, online=True):
    return {'ip': ip, 'mac': '', 'vendor': 'x', 'dtype': 'router' if gw else 'x', 'group': grp, 'name': ip, 'label': None,
            'first_seen': '', 'last_seen': '', 'online': online, 'ports': None, 'is_gw': gw, 'is_self': False}
devs = [dv('192.168.1.254', 'infra', True)] + [dv('192.168.1.%d' % i, g) for i, g in ((10, 'esp'), (11, 'iot'), (12, 'computer'), (13, 'phone'), (14, 'other'))]
fig = Figure(figsize=(6, 4)); mod._nm_dev_iso_draw(fig, mod._nm_dev_layout(devs), None, '192.168.1.254')
ax = fig.axes[0]
lines = [l for l in ax.lines if l.get_zorder() == 1]
check(len(lines) == 5, 'map: a connection line from the router to each of the 5 devices (%d)' % len(lines))
devs2 = [dict(d, is_gw=False) for d in devs]
fig2 = Figure(figsize=(6, 4)); mod._nm_dev_iso_draw(fig2, mod._nm_dev_layout(devs2), None, '10.5.0.1')
check(len([l for l in fig2.axes[0].lines if l.get_zorder() == 1]) == 0, 'map: no router known, no lines (the symptom this fixes)')
print('\nRESULT: ' + ('PASS' if not fails else 'FAIL %d' % len(fails)))
sys.exit(1 if fails else 0)
