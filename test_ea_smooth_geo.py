#!/usr/bin/env python3
"""Topology window: steady frame rate (frames scheduled for what is left of 50 ms, the still Sankey scene redrawn
in full only every BG_REFRESH_S), and the Geo map's Flows slider draws only the busiest N flows.
Run: xvfb-run -a python3.12 test_ea_smooth_geo.py"""
import importlib.util, os, sys, time, random, threading
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
import tkinter as tk
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
root = tk.Tk(); root.withdraw()
st = {}
threading.Timer(60, lambda: os._exit(3)).start()
hosts = ['192.168.1.164'] + ['203.0.113.%d' % i for i in range(1, 40)]
def make():
    ea = mod.EtherApeWindow(tshark_path=None, monitor=None); st['ea'] = ea
    ea._layout_mode = 'sankey'; ea._capturing = True; ea._render_mode = lambda: 'full'
    gaps = []; draws = []; last = [0.0]
    o = ea._render_tick_inner
    def w():
        t = time.perf_counter()
        if last[0]: gaps.append(t - last[0])
        last[0] = t; o()
    ea._render_tick_inner = w
    od = ea._canvas.draw
    def d(*a, **k):
        draws.append(1); return od(*a, **k)
    ea._canvas.draw = d
    st['gaps'] = gaps; st['draws'] = draws
def feed():
    ea = st.get('ea')
    if ea:
        for _ in range(60):
            h = random.choice(hosts[1:12]); ea._pkt_queue.append((hosts[0], h, 'eth:ip:' + random.choice(['tcp', 'udp', 'dns']), random.randint(60, 1400)))
    root.after(50, feed)
def measure_start():
    st['gaps'].clear(); st['draws'].clear()
root.after(200, make); root.after(400, feed); root.after(4000, measure_start); root.after(12000, root.quit)
root.mainloop()
ea = st['ea']; g = sorted(st['gaps'])
med = g[len(g) // 2] * 1000; p95 = g[int(len(g) * .95)] * 1000
check(ea.BG_REFRESH_S >= 1.0, 'the still scene is redrawn in full at most every %.1f s' % ea.BG_REFRESH_S)
check(44 <= med <= 56, 'frames come every ~50 ms (median %.1f ms)' % med)
check(p95 <= 80, 'and evenly (95%% within %.1f ms)' % p95)
check(len(st['draws']) <= 12, 'only a few full redraws in 8 s of busy traffic (%d)' % len(st['draws']))
check(len(ea._nodes) >= 6 and len(ea._flows) >= 6, 'the traffic reached the view (%d hosts, %d flows)' % (len(ea._nodes), len(ea._flows)))

# ── Geo map: Flows slider ──
ea._capturing = False
for i, h in enumerate(hosts[1:]):
    ea._nodes[h] = {'bytes': 1000.0 * (i + 1), 'pkts': 10, 'pos': (0.5, 0.5), 'proto': 'tcp', 'age': 0}
    ea._flows[(hosts[0], h, 'tcp')] = {'bytes': 1000.0 * (i + 1), 'pkts': 10, 'proto': 'tcp', 'age': 0}
    ea._geo_cache[h] = {'lat': -40 + i * 2.0, 'lon': -150 + i * 7.5, 'city': 'C%d' % i, 'country': 'X', 'countryCode': 'XX'}
ea._nodes[hosts[0]] = {'bytes': 1e6, 'pkts': 10, 'pos': (0.5, 0.5), 'proto': 'tcp', 'age': 0}
try:
    ea._open_geo_window()
except Exception as e:
    check(False, 'the Geo map opens (%r)' % e)
gw = getattr(ea, '_geo_window', None)
for _ in range(20): root.update(); time.sleep(0.05)
check(gw is not None and hasattr(gw, '_geo_topn_scale'), 'the Geo map has a Flows slider')
if gw is not None and hasattr(gw, '_geo_topn'):
    gw._redraw_map(); n_all = len(gw._flow_arcs)
    gw._geo_topn.set(10); gw._redraw_map(); n10 = len(gw._flow_arcs)
    check(n_all > 10 and n10 <= 10, 'all flows drawn at ALL (%d), at most 10 at "top 10" (%d)' % (n_all, n10))
    gw._geo_topn.set(300); gw._redraw_map()
    check(len(gw._flow_arcs) == n_all, 'back to ALL draws them all again (%d)' % len(gw._flow_arcs))
# ── look: layout switch, protocol cells, names for this PC's two addresses ──
check(set(getattr(ea, '_layout_seg', {})) == {'sankey', 'radial'}, 'SANKEY | RADIAL is a two-way switch')
was = ea._layout_mode
ea._layout_seg['radial'].invoke(); root.update()
check(ea._layout_mode == 'radial' and ea._layout_seg['radial'].cget('fg') == '#5ef0ff', 'pressing RADIAL switches to radial and lights it')
ea._layout_seg['sankey'].invoke(); root.update()
check(ea._layout_mode == 'sankey', 'pressing SANKEY switches back')
ea._table_tick_inner(); root.update()
rows = [ea._host_tree.item(i, 'values') for i in ea._host_tree.get_children()]
check(rows and all(str(r[4]).startswith('\u25cf ') for r in rows), 'the Proto cells read like "● TCP" (%s)' % (rows[0][4] if rows else '-'))
mod._NM_SELF_IFACE.update({'t': time.time(), 'map': {'192.168.1.164': 'Ethernet', '192.168.1.122': 'Wi-Fi'}})
a = mod._nm_friendly_host('192.168.1.164', 'terminator.home'); b = mod._nm_friendly_host('192.168.1.122', 'terminator')
c = mod._nm_friendly_host('8.8.8.8', 'dns.google')
check(a == 'terminator \u00b7 Ethernet' and b == 'terminator \u00b7 Wi-Fi', "this PC's two addresses are told apart (%s / %s)" % (a, b))
check('\u00b7' not in c, 'other hosts keep their usual name (%s)' % c)
print('\nRESULT:', 'FAIL %d' % len(fails) if fails else 'PASS'); os._exit(1 if fails else 0)
