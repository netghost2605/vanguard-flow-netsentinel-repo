#!/usr/bin/env python3
"""A stuck console (Windows QuickEdit selection) must never freeze the app: console output is queued, the
writer thread may block, the app threads never do.   Run: python3.12 test_console_safe.py"""
import importlib.util, os, sys, threading, time, logging
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

class StuckConsole:
    """Like a console window in QuickEdit selection mode: write() blocks until released."""
    encoding = 'cp1252'
    def __init__(s): s.gate = threading.Event(); s.got = []
    def write(s, t): s.gate.wait(); s.got.append(t); return len(t)
    def flush(s): pass
    def isatty(s): return True

console = StuckConsole()
out = mod._NMNonBlockingOut(console, maxsize=50)
check(out.encoding == 'cp1252' and out.isatty() is True, 'the wrapper looks like a console stream')

lg = logging.getLogger('stuck_test'); lg.setLevel(logging.INFO); lg.propagate = False
lg.addHandler(logging.StreamHandler(out))
done = []
def spam():
    for i in range(500):
        lg.info('line %d — with an em dash', i)
        print('print %d' % i, file=out)
    done.append(1)
ths = [threading.Thread(target=spam, daemon=True) for _ in range(4)]
t0 = time.time()
for t in ths: t.start()
for t in ths: t.join(5)
check(len(done) == 4 and time.time() - t0 < 4, 'four threads logging + printing into a STUCK console all finish at once (%.2fs)' % (time.time() - t0))
check(out._q.qsize() <= 50, 'the queue is bounded; overflow is dropped, not blocked')
console.gate.set()
time.sleep(0.5)
check(len(console.got) > 0, 'when the console is released the queued text is written')

# unencodable text must not kill the writer thread
class Cp1252(StuckConsole):
    def __init__(s): super().__init__(); s.gate.set(); s.enc_ok = []
    def write(s, t):
        t.encode('cp1252'); s.got.append(t); return len(t)
c2 = Cp1252(); o2 = mod._NMNonBlockingOut(c2)
o2.write('plain\n'); o2.write('snowman ☃ and dash —\n'); o2.write('after\n'); time.sleep(0.5)
check(any('after' in g for g in c2.got), 'a character the console cannot show does not stop the output')

# harden: not frozen -> stdout untouched; forced -> wrapped
real_out = sys.stdout
mod._nm_harden_console()
check(sys.stdout is real_out, 'when run from source (not the installed app) stdout is left alone')
mod._nm_harden_console(force=True)
check(isinstance(sys.stdout, mod._NMNonBlockingOut), 'the installed app wraps stdout')
sys.stdout = real_out
check(mod._nm_console_quickedit_off() is False, 'quick-edit switch is a harmless no-op off Windows')

# on Windows the call sequence is right (fake kernel32)
import types
calls = {}
class K:
    class _F:
        def __init__(s, f): s.f = f; s.argtypes = None; s.restype = None
        def __call__(s, *a): return s.f(*a)
    def __init__(s):
        s.GetStdHandle = K._F(lambda n: 123 if n == -10 else 0)
        def gcm(h, ref): ref._obj.value = 0x01F7 | 0x0040 | 0x0010; return 1   # quick edit + mouse on
        s.GetConsoleMode = K._F(gcm)
        def scm(h, m): calls['mode'] = m; return 1
        s.SetConsoleMode = K._F(scm)
import ctypes
ctypes.windll = types.SimpleNamespace(kernel32=K()); sys.platform_real = sys.platform
sys.platform = 'win32'
try:
    r = mod._nm_console_quickedit_off()
finally:
    sys.platform = sys.platform_real
check(r is True and not (calls.get('mode', 0xFFFF) & 0x0040) and (calls.get('mode', 0) & 0x0080), 'QuickEdit is cleared and EXTENDED_FLAGS set (mode %s)' % hex(calls.get('mode', 0)))
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
