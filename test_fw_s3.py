#!/usr/bin/env python3
"""Flash ESP32...: classic ESP32 and ESP32-S3 (Heltec V3) boards. The bundled firmware builds for both, the chip on the port
is detected, the floor (transmitter) number is written into the right place, and the Wi-Fi password never stays behind.
Run: xvfb-run -a python3.12 test_fw_s3.py"""
import importlib.util, os, re, stat, sys, tempfile, shutil, textwrap
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)

# ---- the bundle ----
F = mod._nm_fw_files()
for role in ('recv', 'send'):
    names = set(F[role])
    check({'main/main.c', 'main/battery.h', 'main/font8x8.h', 'main/CMakeLists.txt', 'platformio.ini', 'sdkconfig.defaults', 'CMakeLists.txt'} <= names,
          role + ': main.c, battery.h, font8x8.h, CMake and PlatformIO files are bundled')
    ini = F[role]['platformio.ini']
    check('[env:esp32dev]' in ini and '[env:heltec_wifi_lora_32_V3]' in ini and 'src_dir = main' in ini, role + ': platformio.ini has the classic and the Heltec V3 builds')
    cm = F[role]['main/CMakeLists.txt']
    check('esp_lcd' in cm and 'esp_adc' in cm, role + ': main CMake pulls in the screen and battery components')
    check('CONFIG_IDF_TARGET_ESP32S3' in F[role]['main/main.c'], role + ': screen/battery code is compiled only for the S3')
check('#define CSI_SRC_ID' in F['recv']['main/csi_config.h'] and re.search(r'#define\s+CSI_SRC_ID\s+0x01', F['recv']['main/csi_config.h']), 'recv: floor number lives in csi_config.h (default 1)')
check(re.search(r'#define\s+CSI_SRC_ID\s+0x01', F['send']['main/main.c']), 'send: floor number lives in main.c (default 1)')
check('CSIR' in F['recv']['main/main.c'] and 'CSIR' in F['send']['main/main.c'], 'both carry the channel beacon')
check(not re.search(r'#define\s+CSI_WIFI_PASSWORD\s+"[^"]', F['recv']['main/csi_config.h']), 'the bundle holds no Wi-Fi password')
check(all('\r' not in t for r in F.values() for t in r.values()), 'bundled sources use plain line endings')

# ---- the form's values ----
c, e = mod._nm_fw_clean('recv', 'EE-J23Q7W', 'longenough', '', 6)
check(e == '' and c['src_id'] == 1, 'floor number defaults to 1')
c, e = mod._nm_fw_clean('recv', 'EE-J23Q7W', 'longenough', '', 6, 2)
check(e == '' and c['src_id'] == 2, 'floor 2 accepted')
c, e = mod._nm_fw_clean('send', '', '', '', 11, '2')
check(e == '' and c['src_id'] == 2, 'transmitter accepts the number as text')
for bad in (0, 300, 'x', ''):
    c, e = mod._nm_fw_clean('send', '', '', '', 11, bad)
    check(c is None and 'floor number' in e, 'floor number %r refused' % (bad,))

# ---- what is on the port ----
K = mod._nm_fw_chip_kind
check(K('Detecting chip type... ESP32-S3\nChip is ESP32-S3 (QFN56) (revision v0.2)') == 'esp32s3', 'esptool text: ESP32-S3')
check(K('Chip is ESP32-D0WD-V3 (revision v3.1)') == 'esp32', 'esptool text: classic ESP32 (D0WD)')
check(K('Chip is ESP32-PICO-D4 (revision v1.1)') == 'esp32', 'esptool text: ESP32-PICO')
check(K('A fatal error occurred: This chip is ESP32-S3, not ESP32. Wrong --chip argument?') == 'esp32s3', 'upload error text names the S3')
check(K('Chip is ESP32-C3 (revision v0.4)') == 'other' and K('Chip is ESP32-S2') == 'other' and K('Chip is ESP8266EX') == 'other', 'other chips are recognised as unsupported')
check(K('Failed to connect to ESP32: No serial data received.') == '' and K('') == '', 'no answer means unknown')

# ---- writing the project ----
root = tempfile.mkdtemp()
cl = {'channel': 6, 'ssid': 'EE-J23Q7W', 'password': 'hunter2hunter2', 'bssid': '42:f8:7e:4f:67:11', 'src_id': 2}
d = mod._nm_fw_write_project(root, 'recv', cl)
cfg = open(os.path.join(d, 'main', 'csi_config.h'), encoding='utf-8').read()
check('#define CSI_SRC_ID         0x02' in cfg and 'CSI_WIFI_SSID      "EE-J23Q7W"' in cfg and re.search(r'CSI_CHANNEL\s+6\b', cfg), 'receiver project: floor 2, name and channel written')
for stale in ('sdkconfig.esp32dev', 'sdkconfig.heltec_wifi_lora_32_V3'):
    open(os.path.join(d, stale), 'w').write('old')
d = mod._nm_fw_write_project(root, 'recv', cl)
check(not any(os.path.exists(os.path.join(d, 'sdkconfig.' + e)) for e in mod._NM_FW_ENVS.values()), 'stale sdkconfig files from an earlier build are removed')
ds = mod._nm_fw_write_project(root, 'send', {'channel': 9, 'src_id': 2, 'ssid': '', 'password': '', 'bssid': ''})
mc = open(os.path.join(ds, 'main', 'main.c'), encoding='utf-8').read()
check(re.search(r'#define\s+CSI_SRC_ID\s+0x02\b', mc) and re.search(r'#define\s+CSI_CHANNEL\s+9\b', mc), 'transmitter project: floor 2 and the first channel written')
check(os.path.exists(os.path.join(ds, 'main', 'battery.h')) and os.path.exists(os.path.join(ds, 'main', 'font8x8.h')), 'transmitter project has the S3 helper files')

# ---- flashing with a fake PlatformIO ----
tmp = tempfile.mkdtemp()
fake = os.path.join(tmp, 'pio')
open(fake, 'w').write(textwrap.dedent('''\
    #!%s
    import sys, os
    log = os.environ['FAKE_PIO_LOG']
    open(log, 'a').write(' '.join(sys.argv[1:]) + '\\n')
    env = sys.argv[sys.argv.index('-e') + 1]
    mode = os.environ.get('FAKE_PIO_MODE', 'ok')
    print('building ' + env + ' with password ' + os.environ.get('FAKE_PW', ''))
    if mode == 'ok':
        sys.exit(0)
    if mode == 'is_s3' and env == 'esp32dev':
        print('A fatal error occurred: This chip is ESP32-S3, not ESP32. Wrong --chip argument?')
        sys.exit(2)
    if mode == 'is_classic' and env != 'esp32dev':
        print('A fatal error occurred: This chip is ESP32, not ESP32-S3. Wrong --chip argument?')
        sys.exit(2)
    if mode == 'noconnect':
        print('A fatal error occurred: Failed to connect to ESP32-S3: No serial data received.')
        sys.exit(2)
    sys.exit(0)
''' % sys.executable))
os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
LOG = os.path.join(tmp, 'calls.txt'); os.environ['FAKE_PIO_LOG'] = LOG
def run(mode, kind, role='recv', **kw):
    open(LOG, 'w').close(); os.environ['FAKE_PIO_MODE'] = mode
    lines = []
    cl = {'channel': 6, 'ssid': 'EE-J23Q7W', 'password': 'hunter2hunter2', 'bssid': '', 'src_id': 2}
    os.environ['FAKE_PW'] = cl['password']
    r = mod._nm_fw_flash(role, 'COM5', cl, lines.append, pio=fake, root=tempfile.mkdtemp(), detect=lambda p: (kind, 'x'), **kw)
    calls = [l for l in open(LOG).read().splitlines() if l]
    return r, calls, lines
(ok, msg), calls, lines = run('ok', 'esp32s3')
check(ok and len(calls) == 1 and '-e heltec_wifi_lora_32_V3' in calls[0] and '--upload-port COM5' in calls[0], 'S3 on the port: one build, the Heltec V3 one')
check(any('ESP32-S3' in l for l in lines), 'it tells you which board it found')
check(not any('hunter2hunter2' in l for l in lines), 'the Wi-Fi password is masked in the progress text')
(ok, msg), calls, lines = run('ok', 'esp32')
check(ok and len(calls) == 1 and '-e esp32dev' in calls[0], 'classic ESP32 on the port: the esp32dev build')
(ok, msg), calls, lines = run('is_s3', '')
check(ok and len(calls) == 2 and '-e esp32dev' in calls[0] and '-e heltec_wifi_lora_32_V3' in calls[1], 'unreadable chip, it is an S3: classic tried first, then rebuilt for the S3 by itself')
(ok, msg), calls, lines = run('is_classic', '')
check(ok and len(calls) == 1 and '-e esp32dev' in calls[0], 'unreadable chip, a classic ESP32: the first (classic) build is used and no second try is made')
(ok, msg), calls, lines = run('noconnect', 'esp32s3')
check((not ok) and len(calls) == 1 and 'BOOT' in msg and 'PRG' in msg, 'cannot connect: one try, and the message explains the BOOT/PRG button')
(ok, msg), calls, lines = run('ok', 'other')
check((not ok) and calls == [] and 'not built for' in msg, 'an unsupported chip is refused before anything is built')
(ok, msg), calls, lines = run('ok', 'esp32s3', role='send')
check(ok and len(calls) == 1, 'transmitter flashes the same way')
rootd = tempfile.mkdtemp(); open(LOG, 'w').close(); os.environ['FAKE_PIO_MODE'] = 'ok'
mod._nm_fw_flash('recv', 'COM5', {'channel': 6, 'ssid': 'EE-J23Q7W', 'password': 'hunter2hunter2', 'bssid': '', 'src_id': 1}, lambda l: None,
                 pio=fake, root=rootd, detect=lambda p: ('esp32s3', 'x'))
left = open(os.path.join(rootd, 'csi_recv', 'main', 'csi_config.h'), encoding='utf-8').read()
check('hunter2hunter2' not in left, 'the Wi-Fi password is taken back out of the build folder afterwards')

# explicit env in the form values skips detection
open(LOG, 'w').close()
r = mod._nm_fw_flash('send', 'COM5', {'channel': 6, 'ssid': '', 'password': '', 'bssid': '', 'src_id': 1, 'env': 'esp32dev'}, lambda l: None,
                     pio=fake, root=tempfile.mkdtemp(), detect=lambda p: (_ for _ in ()).throw(AssertionError('should not detect')))
check(r[0] and '-e esp32dev' in open(LOG).read(), 'an explicit board choice skips detection')

# ---- esptool lookup / detect with a fake esptool ----
home = tempfile.mkdtemp()
py = os.path.join(home, '.platformio', 'penv', 'bin', 'python'); tool = os.path.join(home, '.platformio', 'packages', 'tool-esptoolpy', 'esptool.py')
os.makedirs(os.path.dirname(py)); os.makedirs(os.path.dirname(tool))
os.symlink(sys.executable, py)
open(tool, 'w').write("import sys\nprint('esptool.py v4.11.0')\nprint('Detecting chip type... ESP32-S3')\nprint('Chip is ESP32-S3 (QFN56) (revision v0.2)')\n")
fp = os.path.join(home, '.platformio', 'penv', 'bin', 'pio'); open(fp, 'w').write('')
check(mod._nm_fw_find_esptool(fp) == (py, tool), 'esptool is found next to PlatformIO')
kind, txt = mod._nm_fw_detect_chip('COM5', tool=(py, tool))
check(kind == 'esp32s3', 'detect_chip reads the chip from esptool output')
kind, txt = mod._nm_fw_detect_chip('COM5', tool=None) if mod._nm_fw_find_esptool('') is None else ('', '')
check(kind == '', 'no esptool means "unknown", not a crash')

# ---- the dialog ----
import tkinter as tk
root_w = tk.Tk(); root_w.withdraw()
T = mod.THEMES['Ocean']
D = {k: T.get(k, '#000000') for k in ('bg', 'text', 'text2')} if isinstance(T, dict) else {'bg': '#0a1420', 'text': '#c8dff0', 'text2': '#8fb4ce'}
if 'bg' not in T:
    D = {'bg': '#0a1420', 'text': '#c8dff0', 'text2': '#8fb4ce'}
seen = {}
def fake_run(role, port, clean, say):
    seen.update(role=role, port=port, clean=dict(clean)); say('fake run'); return True, 'Flashed.'
h = mod._nm_flash_dialog(root_w, D, list_ports=lambda: [('COM5', 'Silicon Labs CP210x', True)], scan=lambda: [], run_flash=fake_run)
root_w.update()
V = h['vars']
check(V['floor'].get().startswith('1'), 'dialog: floor box starts on 1 - Downstairs')
V['floor'].set(mod._NM_FW_FLOORS[1]); V['role'].set('send'); V['ch'].set('11')
h['fill_ports']([('COM5', 'Silicon Labs CP210x', True)]); root_w.update()
h['flash']()
for _ in range(60):
    root_w.update(); 
    import time; time.sleep(0.05)
    if seen: break
check(seen.get('clean', {}).get('src_id') == 2 and seen.get('role') == 'send' and seen.get('port') == 'COM5', 'dialog: Upstairs gives number 2 to the flash step')
txt = h['out'].get('1.0', 'end')
check('number 2' in txt and 'Upstairs' in txt, 'dialog: says which number it is flashing')
# ---- self-healing firmware is the bundled one ----
_f = mod._nm_fw_files()
for _role, _name in (('recv', 'receiver'), ('send', 'transmitter')):
    _m = _f[_role]['main/main.c']
    check('guardian_task' in _m and 'wd_restart' in _m and 'esp_restart' in _m and 'RTC_NOINIT_ATTR' in _m, '%s firmware: guardian that restarts the board and remembers why' % _name)
    check('NETSENTINEL %s' in _m and 'wd_fmt_up' in _m, '%s firmware: screen shows uptime and what caused the last start' % _name)
    check('esp_timer' in _f[_role]['main/CMakeLists.txt'], '%s firmware: esp_timer is a required component' % _name)
check('IP_EVENT_STA_LOST_IP' in _f['recv']['main/main.c'], 'receiver firmware: handles the router taking the address back')
check('"%s' not in _f['recv']['main/csi_config.h'] and 'CSI_WIFI_PASSWORD  ""' in _f['recv']['main/csi_config.h'], 'receiver firmware: no password is bundled')
root_w.destroy()
print('\nRESULT: ' + ('PASS' if not fails else 'FAIL %d' % len(fails)))
sys.exit(1 if fails else 0)
