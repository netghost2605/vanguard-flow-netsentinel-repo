#!/usr/bin/env python3
"""The CSI tab inside the real Wi-Fi window (xvfb): demo start/stop with the SIMULATED badge,
calibration flow, chips and numbers, copy-raw to the clipboard, port list, error hints,
screenshots with CSI_SHOTS=<dir>.  Run: xvfb-run -a python3.12 test_csi_tab.py"""
import importlib.util, os, sys, time, tempfile, json
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod._NM_BOARDS_OFF = False        # these tests exercise the switched-off ESP32 / Floor / Lidar code
import numpy as np, tkinter as tk
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)
class FM:
    theme_name = 'Ocean'; config = {}
    @property
    def colors(self): return mod.THEMES['Ocean']
root = tk.Tk(); root.withdraw()
sd = tempfile.mkdtemp()
w = mod._NMWifiWatcher(FM(), scan_fn=lambda k: {'kind': k, 'ok': True, 'aps': [], 'raw': ''}, state_dir=sd, use_api=False,
                       threads=False, db=None, alert_fn=lambda *a: None)
win = mod._nm_open_wifi(FM(), watcher=w, state_dir=sd)
st = win._nm_state; csi = st['csi']; root.update()
tabs = [st['nb'].tab(i, 'text').strip() for i in range(st['nb'].index('end'))]
check(tabs == ['Live', 'Networks', 'Activity', 'Signal map', 'CSI (ESP32)'], f'CSI is the fifth tab of the Wi-Fi window ({tabs})')
st['nb'].select(4); root.update()
check(csi['chip_m'].cget('text') == 'NOT CONNECTED', 'idle: chip says not connected')
csi['fill_ports']([('COM3', 'Silicon Labs CP210x USB to UART Bridge (COM3)', True), ('COM1', 'Communications Port (COM1)', False)])
check(csi['port_var'].get().startswith('COM3') and '★' in csi['port_var'].get(), 'ports: the USB-serial bridge is listed, starred and preselected')
csi['fill_ports']([])
check('No USB serial ports' in csi['hint_var'].get(), 'ports: an empty list explains the likely cause (charge-only cable)')
csi['port_var'].set('')                  # no port chosen (an empty list now preselects the Wi-Fi entry)
csi['toggle_conn']()
check('Pick a serial port' in csi['hint_var'].get() and csi['S']['src'] is None, 'connect with no port gives guidance and does not start')
# demo (real time, short)
csi['scen_var'].set('Someone walking about')
csi['toggle_demo'](); time.sleep(1.2); root.update(); csi['draw'](force=True)
check(csi['S']['src'] is not None and 'SIMULATED' in csi['badge'].cget('text'), 'demo: badge says SIMULATED')
check(csi['S']['an'].frames > 60 and 'packets/s' in csi['stats_var'].get(), f"demo: frames flowing ({csi['S']['an'].frames}) and shown ({csi['stats_var'].get()})")
txt_before = csi['S']['src'].copy_text(20)
csi['copy_raw'](); root.update()
try:
    clip = root.clipboard_get()
except Exception:
    clip = ''
check(clip.startswith('CSI_DATA') and len(clip.splitlines()) >= 60 and 'Copied' in csi['hint_var'].get(), 'copy raw data: CSI lines are on the clipboard')
csi['toggle_demo'](); root.update()
check(csi['S']['src'] is None and csi['badge'].cget('text') == '', 'demo: stop clears the badge')
# drive the analyzer with a fake clock for the long scenarios, then draw
clock = [10000.0]
def tab_with_clock():
    return mod._nm_csi_build_tab(tk.Frame(root), mod._NM_WIFI_DASH, win, sd, clock=lambda: clock[0])
fr = tk.Toplevel(root); fr.geometry('1200x760')
ctl2 = mod._nm_csi_build_tab(fr, mod._NM_WIFI_DASH, fr, sd, clock=lambda: clock[0])
fr.update()
an = ctl2['S']['an']; sim = mod._NMCsiSim(seed=21, bpm=15.0)
class FakeSrc:
    lock = __import__('threading').Lock(); bad = 0; error = ''; log = []; raw = []
    def hint(self): return ''
    def stop(self): pass
    def copy_text(self, s=20): return ''
ctl2['S']['src'] = FakeSrc(); ctl2['S']['an'] = an
def feed(state, seconds):
    sim.state = state
    for i in range(int(seconds * 50)):
        t = clock[0] + i / 50.0
        p = mod._nm_csi_parse_line(sim.frame(t)); an.add(t, p['amp'], p['rssi'])
    clock[0] += seconds
feed('empty', 8)
ctl2['draw'](force=True); fr.update()
ctl2['calibrate']()
check('starts in 10 s' in ctl2['cal_var'].get(), 'calibrate: tells you to leave the room, 10 s lead time')
for _ in range(6):
    feed('empty', 2.0); ctl2['draw'](force=True)
check('Calibrating' in ctl2['cal_var'].get() or an.cal is not None, f"calibrate: countdown ends and the 20 s measurement begins ({ctl2['cal_var'].get()[:50]})")
for _ in range(12):
    feed('empty', 2.0); ctl2['draw'](force=True)
check(an.empty is not None and 'Calibrated' in ctl2['cal_var'].get(), f"calibrate: reference stored ({ctl2['cal_var'].get()[:60]})")
feed('empty', 6); ctl2['draw'](force=True)
check('STILL' in ctl2['chip_m'].cget('text') and 'matches' in ctl2['chip_r'].cget('text'), f"empty: chips {ctl2['chip_m'].cget('text')} / {ctl2['chip_r'].cget('text')}")
SHOT = os.environ.get('CSI_SHOTS')
feed('walking', 5); ctl2['draw'](force=True); fr.update()
check('MOTION' in ctl2['chip_m'].cget('text'), f"walking: chip {ctl2['chip_m'].cget('text')}")
if SHOT:
    ctl2['fig'].set_size_inches(12, 5.2); ctl2['fig'].savefig(os.path.join(SHOT, 'csi_walking.png'), dpi=90, facecolor=ctl2['fig'].get_facecolor())
feed('empty', 6)
feed('still', 40); ctl2['draw'](force=True); fr.update()
check(ctl2['breath_var'].get().startswith('breathing: 1') and abs(float(ctl2['breath_var'].get().split()[1]) - 15) <= 2, f"sitting still: {ctl2['breath_var'].get()}")
if SHOT:
    ctl2['fig'].savefig(os.path.join(SHOT, 'csi_breathing.png'), dpi=90, facecolor=ctl2['fig'].get_facecolor())
    import PIL  # full-window screenshot not available under xvfb without extras; the figure image is the evidence
ctl2['clear_cal'](); check(an.empty is None and 'cleared' in ctl2['cal_var'].get(), 'clear calibration works')
ctl2['close'](); fr.destroy(); win.destroy(); root.update()
print('RESULT:', 'FAIL' if fails else 'PASS'); sys.exit(1 if fails else 0)
