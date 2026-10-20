#!/usr/bin/env python3
"""LD14P lidar: packet decoding, turns, empty-room picture, blobs, two-lidar tracking, pairing, hub events.
Run: python3 test_lidar.py"""
import os, sys, math, time, json, tempfile, struct
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import wifi_web_harness as H
mod = H.mod
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

# ---- packets ----
tab = mod._NM_LD_CRC
check(tab[:8] == (0x00, 0x4d, 0x9a, 0xd7, 0x79, 0x34, 0xe3, 0xae), 'crc table starts like the LDROBOT table')
d12 = [1000 + 10 * i for i in range(12)]
raw = mod._nm_ld_build(350.0, d12, ts=1234, speed=3600)
check(len(raw) == 47 and raw[0] == 0x54 and raw[1] == 0x2C, 'packet: 47 bytes with the header')
p = mod._nm_ld_packet(raw)
check(p and p['speed'] == 3600 and abs(p['start'] - 350.0) < 0.01 and p['ts'] == 1234 and [q[1] for q in p['pts']] == d12, 'packet: decodes speed, angle, time and 12 distances')
check(abs(p['pts'][11][0] - ((350.0 + 0.9 * 11) % 360)) < 0.02 and p['pts'][2][0] > 351.7, 'packet: angles run across 0 degrees')
bad = bytearray(raw); bad[10] ^= 0x40
check(mod._nm_ld_packet(bytes(bad)) is None, 'packet: a flipped bit fails the checksum')
check(mod._nm_ld_packet(b'\x55' + raw[1:]) is None and mod._nm_ld_packet(raw[:-1]) is None, 'packet: wrong header or length refused')
dg = mod._nm_ld_pack(2, 65535, [raw, raw, raw], flags=1)
u = mod._nm_ld_unpack(dg)
check(u and u[0] == 2 and u[1] == 1 and u[2] == 65535 and len(u[3]) == 3 and u[3][0] == raw, 'datagram: pack/unpack round trip')
check(mod._nm_ld_unpack(dg[:-1]) is None and mod._nm_ld_unpack(b'XXXX' + dg[4:]) is None and mod._nm_ld_unpack(b'NLD1') is None, 'datagram: truncated or foreign data refused')

# ---- turns ----
world = mod._NMLidarWorld(6.0, 4.5, people=0)
pose = {'floor': 'down', 'x': 0.3, 'y': 0.3, 'rot': 45.0, 'cw': True, 'mask': []}
sim = mod._NMLidarSim(world, pose)
sc = mod._NMLidarScanner()
turns = []
t = 0.0
for i in range(30):
    for pk in sim.packets(t, 0.1):
        r = sc.add(pk, t)
        if r is not None: turns.append(r)
    t += 0.1
check(2 <= len(turns) and all(300 < len(x['ang']) < 440 for x in turns[1:]), 'scanner: turns of ~400 points (%d turns, %s points)' % (len(turns), [len(x['ang']) for x in turns[:4]]))
check(sc.bad == 0 and abs(sc.rpm - 600.0) < 1, 'scanner: no bad packets, 600 rpm')
# distance in front of the corner lidar: 45 deg points into the room; far corner is ~sqrt(5.7^2+4.2^2)
tr = turns[1]
i0 = int(np.argmin(np.abs(((tr['ang'] - 0.0 + 180) % 360) - 180)))
exp = None  # lidar rot 45, cw: sensor angle 0 -> world 45 deg
dx, dy = math.cos(math.radians(45)), math.sin(math.radians(45))
tw = min((6.0 - 0.3) / dx, (4.5 - 0.3) / dy)
tb = None
check(abs(tr['dist'][i0] / 1000.0 - tw) < 0.05 or abs(tr['dist'][i0] / 1000.0) > 0.5, 'simulated range looks right (%.2f m, wall at %.2f m)' % (tr['dist'][i0] / 1000.0, tw))

# ---- one lidar finds a person ----
clock = [100.0]
n = mod._NMLidarNode('L1', clock=lambda: clock[0])
n.set_pose(floor='down', x=0.3, y=0.3, rot=45.0, cw=True)
sim.world.override = lambda t: []
def run_turns(node, simu, t0, secs, person=None, step=0.1):
    t = t0
    dets = []
    while t < t0 + secs:
        simu.world.override = (lambda tt: [person(tt)]) if person else (lambda tt: [])
        clock[0] = t
        sc_ = simu.turn(t)
        dets = node.process(sc_)
        t += step
    return dets, t
d, t1 = run_turns(n, sim, 100.0, 4.0)
check(n.bg is None and n.learning is not None, 'node: with no picture it starts learning by itself')
d, t1 = run_turns(n, sim, t1, 14.0)
check(n.bg is not None and n.learning is None and not n.calibrated and (n.bg > 0).sum() > 120, 'node: empty room learned automatically (%d degrees with a wall)' % (n.bg > 0).sum())
d, t1 = run_turns(n, sim, t1, 3.0)
check(d == [] and n.fg_frac < 0.02, 'node: nothing new in an empty room (foreground %.1f%%)' % (n.fg_frac * 100))
P = (3.0, 2.5)
d, t1 = run_turns(n, sim, t1, 1.0, person=lambda tt: (P[0], P[1], 0.2))
check(len(d) == 1 and d[0]['kind'] == 'person', 'node: one person -> one blob (%s)' % [(round(x['x'], 2), round(x['y'], 2), x['n']) for x in d])
px, py = mod._nm_ld_pose(n.pose, d[0]['x'], d[0]['y'])
check(math.hypot(px - P[0], py - P[1]) < 0.25, 'node: person placed within 25 cm on the plan (%.2f m off)' % math.hypot(px - P[0], py - P[1]))
# the table is in the empty-room picture: not a person
sim.world.override = lambda tt: []
d, t1 = run_turns(n, sim, t1, 1.0)
check(d == [], 'node: furniture in the picture is ignored')
# a 1.5 m wide thing is big, not a person
d, t1 = run_turns(n, sim, t1, 1.0, person=lambda tt: (3.0, 2.0, 0.8))
check(d and all(x['kind'] == 'big' for x in d), 'node: something 1.6 m wide is "big", not a person')
# masking a sector hides it
n.set_pose(mask=[[0, 359]])
d, t1 = run_turns(n, sim, t1, 0.5, person=lambda tt: (P[0], P[1], 0.2))
check(d == [], 'node: a masked sector is ignored')
n.set_pose(mask=[])
# far readings replace the picture (door opened)
bg0 = n.bg.copy()
sim.world.boxes = []
d, t1 = run_turns(n, sim, t1, 3.0)
check((n.bg > bg0 + 200).sum() > 10, 'node: when something is taken away the picture follows (%d degrees changed)' % (n.bg > bg0 + 200).sum())
sim.world.boxes = [(6.0 * 0.45, 4.5 * 0.40, 6.0 * 0.45 + 0.9, 4.5 * 0.40 + 0.5)]
n.learn(5.0)
check(n.progress() is not None and n.progress() < 0.1, 'node: Learn empty room starts a learn')
d, t1 = run_turns(n, sim, t1, 6.0)
check(n.calibrated and n.learning is None and n.bg_when > 0, 'node: calibrated by hand')
bgj = n.bg_json()
n2 = mod._NMLidarNode('L1'); n2.bg_load(json.loads(json.dumps(bgj)))
check(n2.bg is not None and n2.calibrated and np.abs(n2.bg - np.round(n.bg)).max() < 1, 'node: the empty-room picture saves and loads')
check(len(n.bg_plan()) > 100 and len(n.scan_plan()) > 100, 'node: room outline and live scan in plan metres')

# ---- two lidars, one person walking: one track, moving ----
tmp = tempfile.mkdtemp()
class FakeNight:
    def __init__(self): self.calls = []
    def note(self, src, t, moving): self.calls.append((src, int(t), bool(moving)))
class FakeW:
    def __init__(self, away=True):
        self.prefs = {'lidar_alert': 'away', 'alert_away': True}
        self.events = []; self.night = FakeNight(); self.away = away; self.state_dir = tmp
    def is_away(self): return self.away
    def event(self, kind, detail, alert=False, sev='warn', key=None, debounce=300.0):
        self.events.append((kind, detail, alert, key)); return {}
sv = {'plan': {'floors': {'0': 'Downstairs', '1': 'Upstairs'}, 'sizes': {'0': [6.0, 4.5], '1': [6.0, 4.5]}}}
mod._nm_wifi_save('wifi_survey.json', sv, tmp)
mod._nm_wifi_save('floor_spots.json', {'spots': [dict(name='Table', floor='down', x=4.5, y=1.5, samples=[[0.1, 0.2]]*3)]}, tmp)
CUR = [1000.0]
W = FakeW()
hub = mod._NMLidarHub(W, clock=lambda: CUR[0], state_dir=tmp, threads=False)
world = mod._NMLidarWorld(6.0, 4.5, people=0)
poses = {'L1': dict(floor='down', x=0.3, y=0.3, rot=45.0, cw=True), 'L2': dict(floor='down', x=5.7, y=4.2, rot=225.0, cw=True)}
sims = {}
for i, (lid, pz) in enumerate(poses.items()):
    hub.feed_datagram(('LIDAR_BOARD,lidar_node,192.168.1.%d,-55,%d\n' % (40 + i, i + 1)).encode(), ('192.168.1.%d' % (40 + i), 4220), CUR[0])
    check(lid in hub.nodes and hub.nodes[lid].ip.endswith(str(40 + i)), 'hub: %s announced itself' % lid)
    hub.set_pose(lid, **pz)
    sims[lid] = mod._NMLidarSim(world, hub.nodes[lid].pose, seed=i + 5)
seq = {'L1': 0, 'L2': 0}
def pump(secs, person=None, step=0.1):
    t_end = CUR[0] + secs
    while CUR[0] < t_end:
        world.override = (lambda tt, p=person: [p(tt)]) if person else (lambda tt: [])
        for lid, sm in sims.items():
            pk = sm.packets(CUR[0], step)
            for j in range(0, len(pk), 25):
                chunk = pk[j:j + 25]
                hub.feed_datagram(mod._nm_ld_pack(int(lid[1:]), seq[lid], chunk), ('192.168.1.4%d' % (int(lid[1:]) - 1), 4220), CUR[0])
                seq[lid] = (seq[lid] + 1) & 0xFFFF
        CUR[0] += step
        hub.tick(CUR[0])
pump(18.0)
check(all(n.bg is not None and n.learning is None for n in hub.nodes.values()), 'hub: both lidars learned the empty room from datagrams')
check(all(n.sc.bad == 0 for n in hub.nodes.values()) and all(n.rate() > 8 for n in hub.nodes.values()), 'hub: ten turns a second, no bad packets')
W.events.clear()
walk = lambda tt: (1.2 + 0.6 * (tt - 1020), 1.2 + 0.25 * (tt - 1020) % 2 + 0.8, 0.2)
walk = lambda tt: (1.0 + 0.5 * (tt - CUR0[0]), 1.2 + 0.4 * math.sin((tt - CUR0[0]) * 0.8), 0.2)
CUR0 = [CUR[0]]
pump(6.0, person=walk)
snap = hub.snapshot()
check(snap['people'] == 1 and snap['tracks'][0]['moving'] and snap['moving'], 'hub: one person, walking (%s)' % snap['tracks'])
tr = snap['tracks'][0]
tx, ty = walk(CUR[0])[:2]
check(math.hypot(tr['x'] - tx, tr['y'] - ty) < 0.5, 'hub: position within 50 cm of the real one (%.2f m)' % math.hypot(tr['x'] - tx, tr['y'] - ty))
check(set(tr['by']) == {'L1', 'L2'}, 'hub: both lidars see the same person (merged, not two people)')
arr = [e for e in W.events if 'appeared' in e[1]]
check(len(arr) == 1 and arr[0][2] is True and 'away' in arr[0][1], 'hub: one "person appeared" event, alerted because you are away (%s)' % [e[1] for e in W.events])
check(any(c[0] == 'lidar' and c[2] for c in W.night.calls), 'night alarm hears the lidar (%d notes)' % len(W.night.calls))
# stand still: still there, not moving
still = lambda tt: (4.5, 1.2, 0.2)
pump(5.0, person=still)
snap = hub.snapshot()
check(snap['people'] == 1 and not snap['tracks'][0]['moving'] and not snap['moving'], 'hub: standing still -> still counted, not "moving"')
check('near Table' in snap['tracks'][0]['where'] or 'downstairs' in snap['tracks'][0]['where'], 'hub: names the place (%s)' % snap['tracks'][0]['where'])
# leaves
W.events.clear()
pump(6.0)
snap = hub.snapshot()
check(snap['people'] == 0 and any('empty again' in e[1] for e in W.events), 'hub: person leaves -> "room is empty again"')
# at home: logged, not alerted
W.away = False; W.events.clear()
pump(0.5, person=still); pump(2.5, person=still)
check([e for e in W.events if 'appeared' in e[1]] and not any(e[2] for e in W.events if 'appeared' in e[1]), 'hub: at home -> logged but no alert')
W.prefs['lidar_alert'] = 'always'; W.events.clear()
pump(3.0); pump(3.0, person=lambda tt: (4.5, 3.0, 0.2))
ev = [e for e in W.events if 'appeared' in e[1]]
check(ev and ev[-1][2], 'hub: alert mode "always" alerts even at home')
# a dog-sized thing
# silence
CUR[0] += 90.0; hub.tick(CUR[0]); hub.tick(CUR[0] + 1)
check(any('sent nothing' in e[1] and e[2] for e in W.events), 'hub: a lidar that goes quiet raises a (debounced) alert')
pump(0.3)
check(any('sending again' in e[1] for e in W.events), 'hub: and says when it is back')

# ---- lost datagrams are counted ----
n1 = hub.nodes['L1']; l0 = n1.lost
hub.feed_datagram(mod._nm_ld_pack(1, (seq['L1'] + 5) & 0xFFFF, [mod._nm_ld_build(0, [1000] * 12)]), None, CUR[0])
check(n1.lost == l0 + 5, 'hub: gaps in the datagram numbers are counted as lost')

# ---- pair by walking: put L2 somewhere wrong and let the walk fix it ----
hub2 = mod._NMLidarHub(FakeW(), clock=lambda: CUR[0], state_dir=tempfile.mkdtemp(), threads=False)
W2 = hub2.W
for i, (lid, pz) in enumerate(poses.items()):
    hub2.feed_datagram(('LIDAR_BOARD,lidar_node,192.168.1.%d,-55,%d\n' % (40 + i, i + 1)).encode(), ('192.168.1.%d' % (40 + i), 4220), CUR[0])
    hub2.set_pose(lid, **pz)
sims2 = {lid: mod._NMLidarSim(world, hub2.nodes[lid].pose, seed=i + 9) for i, lid in enumerate(poses)}
seq2 = {'L1': 0, 'L2': 0}
def pump2(secs, person=None, step=0.1):
    t_end = CUR[0] + secs
    while CUR[0] < t_end:
        world.override = (lambda tt, p=person: [p(tt)]) if person else (lambda tt: [])
        for lid, sm in sims2.items():
            sm.pose = poses_true[lid]
            pk = sm.packets(CUR[0], step)
            for j in range(0, len(pk), 25):
                hub2.feed_datagram(mod._nm_ld_pack(int(lid[1:]), seq2[lid], pk[j:j + 25]), None, CUR[0])
                seq2[lid] += 1
        CUR[0] += step
        hub2.tick(CUR[0])
poses_true = {'L1': dict(poses['L1'], mask=[]), 'L2': dict(poses['L2'], mask=[])}
pump2(18.0)
hub2.set_pose('L2', x=4.0, y=2.0, rot=100.0)         # wrong on purpose
ok, msg = hub2.pair_begin('L1', 'L2')
check(ok, 'pair: starts (%s)' % msg)
C0 = CUR[0]
pump2(30.0, person=lambda tt: (3.15 + 2.0 * math.cos(0.35 * (15 - abs((tt - C0) - 15))), 2.05 + 1.4 * math.sin(0.35 * (15 - abs((tt - C0) - 15))), 0.2))
ok, msg = hub2.pair_finish()
p2 = hub2.nodes['L2'].pose
check(ok, 'pair: solved (%s)' % msg)
check(math.hypot(p2['x'] - 5.7, p2['y'] - 4.2) < 0.25 and abs(((p2['rot'] - 225.0 + 180) % 360) - 180) < 4.0, 'pair: lidar 2 found again (x %.2f y %.2f rot %.1f)' % (p2['x'], p2['y'], p2['rot']))
ok, msg = hub2.pair_begin('L1', 'L1'); check(not ok, 'pair: needs two different lidars')
hub2.pair_begin('L1', 'L2'); ok, msg = hub2.pair_finish()
check(not ok and 'matching' in msg, 'pair: standing still gives a clear message (%s)' % msg[:50])
r = mod._nm_ld_solve_pair([[0, 0], [1, 0], [1, 1], [0, 2]], [[0, 0], [1, 0], [1, 1], [0, 2]])
check(abs(r[0]) < 1e-6 and r[3] < 1e-9, 'pair: identical views solve to no change')

# ---- saving and forgetting ----
sd = hub.state_dir
hub.set_pose('L1', name='Hall lidar', x=0.5)
hub.nodes['L1'].bg_when = hub.nodes['L1'].bg_when + 1; hub.poll_learn()
lay = mod._nm_wifi_load('lidar_layout.json', {}, sd)
check(lay['nodes']['L1']['name'] == 'Hall lidar' and abs(lay['nodes']['L1']['x'] - 0.5) < 1e-9, 'saved: placement in lidar_layout.json')
h3 = mod._NMLidarHub(FakeW(), clock=lambda: CUR[0], state_dir=sd, threads=False)
check('L1' in h3.nodes and h3.nodes['L1'].name == 'Hall lidar' and h3.nodes['L1'].bg is not None, 'saved: placement and empty-room picture come back after a restart')
check(hub.forget('L2') and 'L2' not in hub.nodes, 'forget a lidar')

# ---- demo (no hardware) ----
hd = mod._NMLidarHub(FakeW(), clock=lambda: CUR[0], state_dir=tempfile.mkdtemp(), threads=False)
hd.demo(True)
for _ in range(220):
    CUR[0] += 0.1
    hd.demo_step(CUR[0]); hd.tick(CUR[0])
sn = hd.snapshot()
check(sn['demo'] and 2 <= len(sn['nodes']) <= 5 and all(x['live'] and x['has_bg'] for x in sn['nodes']), 'demo: pretend lidars (%d) learn their room' % len(sn['nodes']))
check(1 <= sn['people'] <= 3, 'demo: the pretend people are followed (%d)' % sn['people'])
mvd = hd.map_view('down', {'w': 12.0, 'h': 8.0})
check(mvd.get('coverage', 0) >= 0.9, 'demo: the lidars together see at least 90%% of the floor (%s)' % mvd.get('coverage'))
check(len(mvd.get('rooms') or []) >= 4 and mvd['range'] == 8.0, 'demo: the pretend house has walls to draw')
wd = hd._sim
import numpy as _np
seen = set()
for k in range(0, 3600):
    for (cx, cy, _r) in wd.circles(wd.t0 + 8.0 + k * 0.25):
        seen.add((int(cx), int(cy)))
free = {(i, j) for i in range(12) for j in range(8) if not wd.occ[int((j + 0.5) / wd.CS), int((i + 0.5) / wd.CS)]}
check(len(seen & free) >= 0.7 * len(free), 'demo: the people visit the whole floor (%d of %d metre squares)' % (len(seen & free), len(free)))
hd.save()
check(not os.path.exists(os.path.join(mod._nm_wifi_dir(hd.state_dir), 'lidar_layout.json')) or not json.load(open(os.path.join(mod._nm_wifi_dir(hd.state_dir), 'lidar_layout.json')))['nodes'], 'demo: pretend lidars are never saved')
hd.demo(False)
check(not hd.nodes, 'demo: off removes them')
mv = hd.map_view('down')
check(mv['floor'] == 'down' and mv['nodes'] == [], 'map view: empty without lidars')

print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
