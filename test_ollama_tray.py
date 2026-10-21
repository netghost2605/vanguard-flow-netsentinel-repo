#!/usr/bin/env python3
"""Ollama is started through its tray app when there is one. Run: python3 test_ollama_tray.py"""
import importlib.util, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
d = tempfile.mkdtemp()
exe = os.path.join(d, 'ollama.exe'); open(exe, 'w').write('x')
check(mod._nm_ollama_tray_exe(exe) is None, 'no tray app beside it (or not Windows): None')
tray = os.path.join(d, 'ollama app.exe'); open(tray, 'w').write('x')
real_name = os.name
if os.name == 'nt':
    check(mod._nm_ollama_tray_exe(exe) == tray, 'tray app found beside ollama.exe on Windows')
else:
    check(mod._nm_ollama_tray_exe(exe) is None, 'not Windows: always the plain server')
    mod.os.name = 'nt'
    try:
        check(mod._nm_ollama_tray_exe(exe) == tray, 'tray app found beside ollama.exe (Windows path simulated)')
        check(mod._nm_ollama_tray_exe(None) is None and mod._nm_ollama_tray_exe('') is None, 'no binary: None')
    finally:
        mod.os.name = real_name
src = open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read()
check("subprocess.Popen([tray], **kw)" in src and "subprocess.Popen([exe, 'serve'], **kw)" in src, 'falls back to a plain server when there is no tray app')
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); sys.exit(1 if fails else 0)
