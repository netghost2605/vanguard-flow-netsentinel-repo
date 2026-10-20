"""Serve the real /csi page with synthetic boards: one board in the CSI tab, two floor links in the Floor window,
a week of floor history and a few hours of board history (for tests and previews)."""
import os, sys, time, math, random, threading, tempfile, json
import numpy as np
import wifi_web_harness as H
mod = H.mod


class FS:
    """A source stand-in: what the page needs from _NMCsiSource."""
    def __init__(self, an):
        self.an = an
        self.lock = threading.RLock()
        self.bad = 0
        self.battery = {}
        self.board = None

    def hint(self):
        return ''

    def alive(self):
        return True

    def stop(self):
        pass

    def feed(self, line, t):
        p = mod._nm_csi_parse_line(line)
        if p is not None:
            with self.lock:
                self.an.add(t, p['amp'], p['rssi'])


def make(port=None, seed_week=True):
    port, mon, w, srv = H.make(port, moving=False)
    sd = w.state_dir
    now = time.time()
    # ---- the CSI tab's board -------------------------------------------------------------------
    an = mod._NMCsiAnalyzer()
    fs = FS(an)
    sim = mod._NMCsiSim(seed=3)
    state = {'b': 'empty', 'u': 'empty', 'd': 'empty'}
    t = now - 150.0
    sim.state = 'empty'
    cal_started = False
    while t < now:
        if t > now - 120 and not cal_started:
            an.start_calibration(t, 10.0)
            cal_started = True
        sim.state = 'walking' if (now - 70 < t < now - 40) else 'empty'
        fs.feed(sim.frame(t), t)
        t += 0.04
    w.csi_tab = {'an': an, 'src': fs}
    # ---- the floors ------------------------------------------------------------------------------
    det = mod._NMFloorDetector()
    loc = mod._NMSpotLocator()
    SP = {'spots': [dict(name=n, floor=f, x=x, y=y, samples=[[0.1, 0.2], [0.2, 0.1], [0.15, 0.15]])
                    for (n, f, x, y) in (('Kitchen', 'down', 3.0, 2.5), ('Hall', 'down', 8.0, 4.0), ('Landing', 'up', 5.0, 4.0), ('Bedroom', 'up', 9.0, 2.0))]}
    loc.load(SP)
    sims = {'up': mod._NMCsiSim(seed=11), 'down': mod._NMCsiSim(seed=12)}
    srcs = {f: FS(det.an[f]) for f in ('up', 'down')}
    for f in ('up', 'down'):
        srcs[f].battery = {'rx': {'mv': 3900, 'pct': 70, 't': time.time(), 'id': 'A1'}}
    t = now - 60.0
    while t < now:
        for f in ('up', 'down'):
            sims[f].state = 'walking' if (f == 'up' and now - 30 < t) else 'empty'
            srcs[f].feed(sims[f].frame(t), t)
        t += 0.04
    w.floor_win = {'det': det, 'loc': loc, 'src': srcs}
    mod._nm_wifi_save('floor_layout.json', {'up': {'tx': [1.5, 1.5], 'rx': [10.0, 5.5]}, 'down': {'tx': [1.0, 6.0], 'rx': [10.5, 2.0]}}, sd)
    mod._nm_wifi_save('floor_spots.json', SP, sd)
    w.prefs['floor_bg'] = False

    def feeder():
        tt = time.time()
        while True:
            time.sleep(0.04)
            n = time.time()
            while tt < n:
                sim.state = 'walking' if state['b'] == 'walk' else 'empty'
                fs.feed(sim.frame(tt), tt)
                for f in ('up', 'down'):
                    sims[f].state = 'walking' if state['u' if f == 'up' else 'd'] == 'walk' else 'empty'
                    srcs[f].feed(sims[f].frame(tt), tt)
                tt += 0.04
            try:
                det.tick()
            except Exception:
                pass
    threading.Thread(target=feeder, daemon=True).start()
    # ---- the week of floor history ---------------------------------------------------------------
    h = w.floor_history()
    if seed_week:
        rnd = random.Random(4)
        m1 = int(now // 60)
        for m in range(m1 - 7 * 1440, m1 + 1):
            for f in ('up', 'down'):
                if rnd.random() < 0.97:
                    h.cov[f].add(m)
            hh = (m // 60) % 24
            if rnd.random() < (0.30 if hh in (7, 8, 18, 19, 20, 21) else 0.03):
                f = rnd.choice(('up', 'down'))
                h.ev[f][m] = [float(rnd.randint(8, 55)), float(rnd.randint(15, 60)), rnd.choice(('Kitchen', 'Hall')) if f == 'down' else rnd.choice(('Landing', 'Bedroom'))]
        h.dirty = True
    # ---- a few hours of board history ----------------------------------------------------------------
    db = w.csi_hist_db()
    rr = np.random.RandomState(2)
    sess = db.start_session(now - 3 * 3600, 'live', 'test')
    for k in range(3 * 3600, 150, -1):
        tt = now - k
        mv = (int(tt) // 900) % 4 == 0 and (int(tt) % 900) < 90
        sc = (25 + rr.rand() * 20) if mv else rr.rand() * 4
        db.add(tt, sess, {'moving': mv, 'ready': True, 'calibrated': True, 'turb': sc / 100.0, 'thr': 0.12, 'mu': 0.05, 'score': sc,
                          'room': 'match', 'rssi': -48, 'rate': 25, 'breath': {'bpm': None}}, rr.rand(8) * (3 if mv else 0.6))
    db.flush()
    return port, mon, w, srv, state


if __name__ == '__main__':
    port, mon, w, srv, state = make(int(sys.argv[1]) if len(sys.argv) > 1 else None)
    print('PORT', port, flush=True)
    time.sleep(3600)
