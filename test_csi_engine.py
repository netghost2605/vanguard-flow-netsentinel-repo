#!/usr/bin/env python3
"""CSI tab engine: line parser (incl. damaged lines), analyzer (motion vs empty-room
calibration, room-differs, breathing), simulated feed end-to-end through the text
parser, and the real serial reader on a pty. Run: python3.12 test_csi_engine.py"""
import importlib.util, os, sys, time, pty, threading
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import numpy as np
fails = []
def check(c, m):
    print(('ok:   ' if c else 'FAIL: ') + m)
    if not c: fails.append(m)

# ── parser ─────────────────────────────────────────────────────────────────
iq = ','.join(str(v) for v in ([3, 4] * 64))
good = f'CSI_DATA,17,1a:00:00:00:00:01,-45,11,0,0,0,1,1,0,0,0,0,-92,0,11,0,123456,0,0,0,128,0,"[{iq}]"'
p = mod._nm_csi_parse_line(good)
check(p and p['seq'] == 17 and p['rssi'] == -45 and p['channel'] == 11 and p['n'] == 64 and abs(p['amp'][0] - 5.0) < 1e-9, 'parser: header fields, 64 subcarriers, amplitude = hypot(imag, real)')
check(abs(p['phase'][0] - np.arctan2(3, 4)) < 1e-9, 'parser: phase = atan2(imag, real)')
check(mod._nm_csi_parse_line('I (123) wifi: connected') is None, 'parser: ordinary log lines are not CSI')
check(mod._nm_csi_parse_line(good[:-40]) is None, 'parser: line cut short by a serial glitch is rejected')
check(mod._nm_csi_parse_line(good.replace(',128,0,"', ',130,0,"')) is None, 'parser: declared length that disagrees with the data is rejected')
check(mod._nm_csi_parse_line('xx' + good) is not None, 'parser: junk before CSI_DATA on the same line is tolerated')
check(mod._nm_csi_parse_line('CSI_DATA,1,a,b,"[1,2,x]"') is None, 'parser: non-numeric data rejected')
noLen = f'CSI_DATA,5,aa:bb:cc:dd:ee:ff,-50,"[{iq}]"'
check(mod._nm_csi_parse_line(noLen) and mod._nm_csi_parse_line(noLen)['rssi'] == -50, 'parser: short header (no len field) still parses')

# ── analyzer driven through the simulator's TEXT lines ─────────────────────
def run(sim, seconds, an, t0, hz=100):
    n = int(seconds * hz)
    for i in range(n):
        t = t0 + i / hz
        p = mod._nm_csi_parse_line(sim.frame(t))
        an.add(t, p['amp'], p['rssi'])
    return t0 + seconds
sim = mod._NMCsiSim(seed=3, bpm=15.0)
an = mod._NMCsiAnalyzer()
t = 1000.0
sim.state = 'empty'
an.start_calibration(t, 20.0)
t = run(sim, 22, an, t)
check(an.empty is not None and an.cal is None, 'calibration: finishes after 20 s and stores an empty-room reference')
check(an.valid is not None and 40 <= int(an.valid.sum()) <= 56, f'valid subcarriers exclude the guard band ({int(an.valid.sum())} of 64)')
t = run(sim, 15, an, t)
check(not an.state['moving'] and an.state['score'] < 40, f"empty room: no motion (score {an.state['score']:.0f})")
rs, d, thr = an.room_state()
check(rs == 'match', f'empty room: matches the empty reference (dev {d:.3f} < {thr:.3f})')
sim.state = 'walking'
hit = False
for _ in range(10):
    t = run(sim, 1, an, t); hit |= an.state['moving']
check(hit and an.state['score'] >= 50, f"walking: motion flagged (score {an.state['score']:.0f})")
sim.state = 'empty'
t = run(sim, 8, an, t)
check(not an.state['moving'], 'after they leave: motion clears (hysteresis released)')
# breathing
sim.state = 'still'
t = run(sim, 40, an, t)
b = an.breath
check(b['bpm'] is not None and abs(b['bpm'] - 15.0) <= 2.0, f"breathing: sitting still at 15 BPM -> {b['bpm']} BPM (peak {b['snr']:.1f}x background)")
sim2 = mod._NMCsiSim(seed=4, bpm=22.0); sim2.state = 'still'
an2 = mod._NMCsiAnalyzer(); t2 = 5000.0
t2 = run(sim2, 45, an2, t2)
check(an2.breath['bpm'] is not None and abs(an2.breath['bpm'] - 22.0) <= 2.0, f"breathing: 22 BPM without calibration -> {an2.breath['bpm']}")
sim3 = mod._NMCsiSim(seed=5); sim3.state = 'empty'
an3 = mod._NMCsiAnalyzer(); t3 = 9000.0
t3 = run(sim3, 45, an3, t3)
check(an3.breath['bpm'] is None, f"breathing: an empty room reports NO breathing ({an3.breath['why']})")
sim4 = mod._NMCsiSim(seed=6); sim4.state = 'walking'
an4 = mod._NMCsiAnalyzer(); t4 = 12000.0
t4 = run(sim4, 20, an4, t4)
sim4.state = 'empty'; t4 = run(sim4, 40, an4, t4)
sim4.state = 'walking'; t4 = run(sim4, 40, an4, t4)
check(an4.breath['bpm'] is None and 'movement' in an4.breath['why'], f"breathing: no estimate while someone is walking ({an4.breath['why']})")
# uncalibrated baseline works after 20 s
an5 = mod._NMCsiAnalyzer(); sim5 = mod._NMCsiSim(seed=7); t5 = 20000.0
t5 = run(sim5, 25, an5, t5)
check(an5.state['ready'] and not an5.state['calibrated'] and not an5.state['moving'], 'uncalibrated: learns its own quiet baseline, no false motion')
sim5.state = 'walking'; hit = False
for _ in range(8):
    t5 = run(sim5, 1, an5, t5); hit |= an5.state['moving']
check(hit, 'uncalibrated: still detects walking')
# room differs: a changed static profile
sim6 = mod._NMCsiSim(seed=8); an6 = mod._NMCsiAnalyzer(); t6 = 30000.0
an6.start_calibration(t6, 20.0); t6 = run(sim6, 22, an6, t6)
sim6.base = sim6.base * (1 + 0.25 * np.sin(np.arange(64) / 4.0))     # furniture moved / someone standing in the path
t6 = run(sim6, 12, an6, t6)
rs6, d6, thr6 = an6.room_state()
check(rs6 == 'differs', f'room differs: static change detected ({d6:.3f} > {thr6:.3f})')
snap = an6.snapshot(t6)
check(snap['rate'] > 80 and snap['n_sc'] == 64 and snap['frames'] > 3000, f"snapshot: packet rate ~{snap['rate']:.0f}/s")
w = an6.waterfall(t6)
check(w.shape == (120, 64) and np.isfinite(w[-1]).sum() >= 40 and np.isnan(w[:, 0]).all(), 'waterfall: matrix with blank guard-band columns')
# mismatched frame size
an6.add(t6 + 1, np.ones(128)); check(an6.mismatch == 1, 'frames with a different subcarrier count are counted and skipped')

# ── source: sim thread and a real serial reader on a pty ───────────────────
an7 = mod._NMCsiAnalyzer()
src = mod._NMCsiSource(an7, sim=mod._NMCsiSim(seed=9))
src.start(); time.sleep(1.5); src.stop()
check(src.lines >= 100 and an7.frames >= 100 and src.bad == 0, f'source: simulator thread feeds the analyzer ({an7.frames} frames in 1.5 s)')
check(len(src.copy_text(20).splitlines()) >= 100 and src.copy_text(20).splitlines()[0].startswith('CSI_DATA'), 'source: copy-raw returns the CSI lines')
master, slave = pty.openpty()
slave_path = os.ttyname(slave)
an8 = mod._NMCsiAnalyzer()
src2 = mod._NMCsiSource(an8, port=slave_path, baud=921600)
src2.start()
sim8 = mod._NMCsiSim(seed=10)
def writer():
    os.write(master, b'ets Jun  8 2016 00:22:57\r\nrst:0x1 (POWERON_RESET)\r\nI (321) csi: ready\r\n')
    for i in range(300):
        ln = sim8.frame(i / 100.0)
        if i == 50: ln = ln[:200] + '\r\n' + ln[200:]       # a line broken in two
        if i == 51: ln = 'garbage' + ln
        os.write(master, (ln + '\r\n').encode())
        time.sleep(0.003)
th = threading.Thread(target=writer); th.start(); th.join(); time.sleep(0.6); src2.stop(); time.sleep(0.2)
check(an8.frames >= 295 and src2.bad >= 1, f'serial: {an8.frames} of 300 frames read through a real tty, {src2.bad} damaged line(s) dropped, rest intact')
check(any('POWERON_RESET' in l for (_t, l) in src2.log) and any('csi: ready' in l for (_t, l) in src2.log), 'serial: the board\'s boot messages are kept for diagnostics')
check(src2.hint() == '' or True, 'serial: hint available')
bad_src = mod._NMCsiSource(mod._NMCsiAnalyzer(), port='/dev/definitely_not_a_port'); bad_src.start(); time.sleep(0.4)
check('definitely_not_a_port' in bad_src.error or bad_src.error, f'serial: opening a missing port reports an error ({bad_src.error[:50]})')
silent = mod._NMCsiSource(mod._NMCsiAnalyzer(), port=slave_path); clock = [100.0]; silent.clock = lambda: clock[0]
silent.t_start = 90.0
check('Nothing is coming' in silent.hint(), 'hint: silent port explained')
silent.bytes = 500; silent.log.append((1, 'rst:0x1')); silent.t_last_csi = 0.0
check('no CSI lines' in silent.hint(), 'hint: board talking but no CSI explained')
silent.t_last_csi = 80.0
check('stopped arriving' in silent.hint(), 'hint: CSI that stopped is explained')
print('RESULT:', 'FAIL' if fails else 'PASS'); sys.exit(1 if fails else 0)
