#!/usr/bin/env python3
"""Windows Location off: the Wi-Fi watcher says so instead of 'waiting for the first scan'. Run: xvfb-run -a python3 test_loc_blocked.py"""
import importlib.util, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
import wifi_web_harness as H
port, mon, w, srv = H.make(moving=False)
check(w.blocked_msg() == '', 'no message while Wi-Fi works')
w._on_api_msg({'k': 'err', 'msg': 'BssList 5'})
check(w.blocked_msg() == mod._NM_LOC_MSG, 'helper error 5 (access denied) -> Location message')
snap = w.snapshot()
check(snap['blocked'] == mod._NM_LOC_MSG, 'snapshot carries it for the 3D overlay')
check(mod._NM_LOC_MSG in w.web_view()['errors'], 'page errors include it')
w._on_api_msg({'k': 'bss', 'aps': []})
check(w.blocked_msg() == '', 'cleared when Windows answers again')
w._on_api_msg({'k': 'err', 'msg': 'BssList 87'})
check(w.blocked_msg() == '', 'other helper errors do not claim Location is off')
# netsh wording
orig = mod._nm_run
mod._NM_IS_WIN = True
mod._nm_run = lambda cmd, timeout=8: (1, 'There is 1 interface on the system:\nNetwork shell commands need location permission to access WLAN information.\n')
r = mod._nm_wifi_scan('link'); mod._nm_run = orig
check(r['error'] == mod._NM_LOC_MSG and not r['ok'], 'netsh location refusal -> Location message')
print('ALL PASS' if not fails else 'FAILED: %d' % len(fails)); os._exit(1 if fails else 0)
