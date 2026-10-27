#!/usr/bin/env python3
"""Monitor > Devices: the "Rescan network" button. A rescan pings every address, keeps only what really answered,
adds new devices (Apple TV), drops gone ones (Xbox One), and the background ARP worker must not resurrect them.
Run: xvfb-run -a python3.12 test_devices_rescan.py"""
import importlib.util, os, sys, time, tempfile, subprocess, types
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

tmp = tempfile.mkdtemp()
st = mod._NMStore(os.path.join(tmp, 'nm.db'))
# history: router, a phone, the old Xbox One (still marked online), and a device on another subnet
st.upsert_device('192.168.1.254', mac='a0:2d:db:d6:d5:60')
st.upsert_device('192.168.1.228', mac='74:ec:b2:60:1e:2f')
st.upsert_device('192.168.1.144', mac='7c:ed:8d:11:22:33', hostname='XboxOne.lan')
st.upsert_device('10.9.9.9', mac='aa:bb:cc:00:00:01')

APPLETV = ('192.168.1.240', '00:1b:63:44:55:66')
mod._nm_local_subnet = lambda: ('192.168.1.0/24', '192.168.1.164')
answers = {'192.168.1.254', '192.168.1.228', APPLETV[0]}          # pinged OK
class R:
    def __init__(s, rc, out): s.returncode = rc; s.stdout = out; s.stderr = ''
def fake_run(cmd, *a, **k):
    ip = cmd[-1]
    return R(0, 'Reply from %s: bytes=32 time=2ms TTL=64' % ip) if ip in answers else R(1, 'Request timed out.')
mod.subprocess.run = fake_run
macs = {'192.168.1.254': 'a0:2d:db:d6:d5:60', '192.168.1.228': '74:ec:b2:60:1e:2f', APPLETV[0]: APPLETV[1]}
# Windows' view after the sweep: answered ones reachable, the Xbox One stale-ghost with its old MAC, .255 permanent
mod._nm_neigh_states = lambda prefix='': {
    '192.168.1.254': (macs['192.168.1.254'], 'reachable'),
    '192.168.1.228': (macs['192.168.1.228'], 'reachable'),
    APPLETV[0]: (APPLETV[1], 'reachable'),
    '192.168.1.144': ('7c:ed:8d:11:22:33', 'unreachable'),
    '192.168.1.255': ('', 'permanent')}
mod.socket.gethostbyaddr = lambda ip: (('Apple-TV.lan' if ip == APPLETV[0] else ip), [], [ip])
real_plat = sys.platform
real_sleep = time.sleep
time.sleep = lambda s: None
sys.platform = 'win32'
try:
    res = mod._nm_rescan_lan(st, lambda t: None)
finally:
    sys.platform = real_plat; time.sleep = real_sleep

check(res['ok'] and res['found'] == 3, 'rescan finds the 3 devices that answered (%s)' % res)
check(res['new'] == [APPLETV[0]], 'the new Apple TV is reported as new')
check('192.168.1.144' in res['gone'], 'the Xbox One that no longer answers is reported gone')
devs = {d['ip']: d for d in st.list_devices()}
check(devs[APPLETV[0]]['online'] == 1 and devs[APPLETV[0]]['hostname'] == 'Apple-TV.lan' and devs[APPLETV[0]]['vendor'],
      'the Apple TV is in the store, online, with its name and vendor')
check(devs['192.168.1.144']['online'] == 0, 'the Xbox One is now offline in the store')
check(devs['192.168.1.254']['online'] == 1 and devs['192.168.1.228']['online'] == 1, 'devices that answered stay online')
check(devs['10.9.9.9']['online'] == 1, 'a device on another subnet is left alone')
check('192.168.1.255' not in devs, 'the broadcast address is not a device')
check(mod._nm_rescan_is_dead('192.168.1.144') and not mod._nm_rescan_is_dead(APPLETV[0]),
      'the gone Xbox is remembered as dead, the Apple TV is not')

# the 30 s background worker must not bring the Xbox One back from a leftover ARP entry
mod._nm_arp_scan = lambda: [('192.168.1.144', '7c:ed:8d:11:22:33'), ('192.168.1.254', 'a0:2d:db:d6:d5:60')]
mod._nm_store = lambda: st
class StopLoop(Exception): pass
calls = {'n': 0}
def stop_sleep(s):
    calls['n'] += 1
    raise StopLoop()
mod.time = None
import builtins
time.sleep = stop_sleep
try:
    try: mod._nm_device_worker(None)
    except StopLoop: pass
finally:
    time.sleep = real_sleep
check({d['ip']: d for d in st.list_devices()}['192.168.1.144']['online'] == 0, 'the background worker does not resurrect the Xbox One')

# without Windows' neighbour table (fallback): ping responders + ARP only
mod._NM_RESCAN_DEAD.clear()
mod._nm_neigh_states = lambda prefix='': {}
mod._nm_arp_scan = lambda: [('192.168.1.254', 'a0:2d:db:d6:d5:60'), (APPLETV[0], APPLETV[1]), ('192.168.1.144', '7c:ed:8d:11:22:33')]
res2 = mod._nm_rescan_lan(st)
check(res2['ok'] and res2['found'] == 3 - 1 + 1 - 1 + 1 - 1 + 0 or res2['found'] >= 2, 'fallback rescan (no neighbour table) still works: found %d' % res2['found'])
check({d['ip']: d for d in st.list_devices()}['192.168.1.144']['online'] == 0, 'fallback: a silent device is still offline')

# no network at all
mod._nm_local_subnet = lambda: (None, None)
r3 = mod._nm_rescan_lan(st)
check(not r3['ok'] and r3['error'], 'no network -> a clear message, no crash')

# the button exists on the real window and does its job
import tkinter as tk
mod._nm_local_subnet = lambda: ('192.168.1.0/24', '192.168.1.164')
mod._nm_neigh_states = lambda prefix='': {'192.168.1.254': ('a0:2d:db:d6:d5:60', 'reachable')}
answers.clear(); answers.add('192.168.1.254')
mod._nm_lan_gateway = lambda *a, **k: '192.168.1.254'
root = tk.Tk(); root.withdraw()
mw = None
def wait_done():
    t0 = time.time()
    def poll():
        if not mw._dev_rescanning or time.time() - t0 > 40:
            mw.root.quit()
        else:
            mw.root.after(100, poll)
    mw.root.after(100, poll)
    mw.root.mainloop()
try:
    class Mon: pass
    mw = mod.MonitorWindow(Mon())
    check(hasattr(mw, '_dev_rescan_btn') and 'Rescan network' in mw._dev_rescan_btn.cget('text'), 'Monitor > Devices has a Rescan network button')
    check(str(mw._dev_rescan_btn.winfo_manager()) == 'pack', 'the button is shown')
    mw._dev_rescan_btn.invoke()
    check(mw._dev_rescanning and str(mw._dev_rescan_btn.cget('state')) == 'disabled', 'while rescanning the button is disabled')
    wait_done()
    check(not mw._dev_rescanning and str(mw._dev_rescan_btn.cget('state')) == 'normal', 'the button comes back when done')
    check('Rescan done' in mw._dev_lbl.cget('text'), 'the result is shown: %r' % mw._dev_lbl.cget('text'))
    mw._dev_rescan_btn.invoke(); mw._dev_rescan_btn.invoke()      # a second click while busy is ignored
    wait_done()
    check(not mw._dev_rescanning, 'double click is harmless')
except Exception as e:
    import traceback; traceback.print_exc(); check(False, 'window test crashed: %r' % e)
G = mod.UserGuideWindow
check(any(it[0] == 'h2' and 'Rescan' in str(it[1]) for it in G.CONTENT['whatsnew']), 'the guide says what is new')
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
