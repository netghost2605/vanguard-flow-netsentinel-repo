#!/usr/bin/env python3
"""The Honeypot window reads attacks from T-Pot (Elasticsearch) instead of opening decoy ports itself.
Run: python3 test_tpot_feed.py   (xvfb not needed)"""
import importlib.util, os, sys, time, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod._NM_HONEYPOT_OFF = False        # the dormant honeypot code is tested with the switch ON
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
now = time.time()
DOCS = [
 {'_id': 'a1', '_source': {'@timestamp': iso(now - 50), 'type': 'Cowrie', 'src_ip': '203.0.113.9', 'dest_port': '22', 'proto': 'tcp',
                          'eventid': 'cowrie.login.failed', 'username': 'root', 'password': '123456'}},
 {'_id': 'a2', '_source': {'@timestamp': iso(now - 40), 'type': 'Dionaea', 'src_ip': '::ffff:198.51.100.7', 'dest_port': 21, 'protocol': 'ftp'}},
 {'_id': 'a3', '_source': {'@timestamp': iso(now - 30), 'type': 'Sentrypeer', 'src_ip': '192.0.2.44', 'dest_port': 5060, 'proto': 'UDP', 'msg': 'INVITE sip:100@x'}},
 {'_id': 'a4', '_source': {'@timestamp': iso(now - 20), 'type': 'Wordpot', 'src_ip': '172.18.0.1', 'dest_port': 80, 'http': {'http_method': 'GET', 'url': '/wp-login.php'}}},
 {'_id': 'a5', '_source': {'@timestamp': iso(now - 10), 'type': 'Cowrie', 'src_ip': '', 'dest_port': 22}},
]
calls = []
def fake(url, body=None):
    calls.append((url, body))
    if url.endswith('/_cluster/health'): return {'status': 'green'}
    since = body['query']['bool']['filter'][0]['range']['@timestamp']['gte']
    return {'hits': {'hits': [d for d in DOCS if d['_source']['@timestamp'] >= since]}}

saved = {}
hits_seen = []
hp = mod._NMTpotHoneypot(on_hit=lambda r, c: hits_seen.append((r, c)), fetch=fake,
                         cursor_load=lambda: saved.get('ts'), cursor_save=lambda t: saved.__setitem__('ts', t))
hp._ts = now - 3600
n = hp.poll()
H = hp.hits()
check(n == 4 and len(H) == 4, 'four events filed, the one without a source address skipped (%d)' % n)
c = [h for h in H if h['ip'] == '203.0.113.9'][0]
check(c['service'] == 'Cowrie' and c['port'] == 22 and c['sample'] == 'root:123456' and c['tool'] == 'login failed', 'Cowrie login attempt mapped: %s' % c)
check(abs(c['time'] - (now - 50)) < 1.0, 'uses the event time, not the time we polled')
d = [h for h in H if h['service'] == 'Dionaea'][0]
check(d['ip'] == '198.51.100.7' and d['port'] == 21, 'IPv6-mapped address cleaned')
u = [h for h in H if h['service'] == 'Sentrypeer'][0]
check(u['proto'] == 'udp' and u['sample'].startswith('INVITE'), 'UDP event and message sample')
w = [h for h in H if h['service'] == 'Wordpot'][0]
check(w['masked'] is True and w['sample'] == 'GET /wp-login.php', 'a Docker gateway source is flagged masked, URL sampled')
check(not any(h.get('masked') for h in H if h['ip'] != '172.18.0.1'), 'real addresses are not flagged')
hp_d = mod._NMTpotHoneypot(fetch=fake, cursor_load=lambda: None, cursor_save=lambda t: None)
hp_d._record('192.168.80.1', 22, b'', force=True, service='Cowrie', tool='')
check(hp_d.hits()[-1].get('masked') is True, 'a Docker custom-network gateway (192.168.80.1) is masked too')
hp_d._record('203.0.113.50', 22, b'', force=True, service='Cowrie', tool='')
check(not hp_d.hits()[-1].get('masked'), 'a public address is not masked')
check(len(hits_seen) == 4, 'on_hit called for each')
body = calls[-1][1]
check({'terms': {'type.keyword': ['Suricata', 'P0f', 'Fatt', 'NGINX', 'Nginx']}} in body['query']['bool']['must_not'] and any('eventid.keyword' in m['terms'] for m in body['query']['bool']['must_not']), 'network-monitor events are excluded in the query')
check(saved.get('ts') and saved['ts'] > now - 15, 'cursor saved at the newest event')

# second poll: nothing is filed twice
n2 = hp.poll()
check(n2 == 0 and len(hp.hits()) == 4, 'the same events are not filed again')
# a restart resumes from the saved cursor, no duplicates of old events
hp2 = mod._NMTpotHoneypot(fetch=fake, cursor_load=lambda: saved.get('ts'), cursor_save=lambda t: None)
hp2.poll()
check(len(hp2.hits()) <= 1, 'a new session resumes at the cursor (%d re-read)' % len(hp2.hits()))

# summary / start / errors
s = hp.summary()
check(s['source'] == 'tpot' and s['total'] == 4 and s['unique_ips'] == 4 and s['types'].get('Cowrie') == 1, 'summary says T-Pot and counts types')
hp3 = mod._NMTpotHoneypot(fetch=fake, cursor_load=lambda: None, cursor_save=lambda t: None)
check(hp3.start() == 1 and hp3._running, 'start connects when T-Pot answers')
hp3.stop(); check(not hp3._running, 'stop')
def down(url, body=None): raise OSError('refused')
hp4 = mod._NMTpotHoneypot(fetch=down)
check(hp4.start() == 0 and 'tpot_start.ps1' in hp4.error, 'start explains how to start T-Pot when it is down')
check(mod._nm_hp_start_error(hp4) == hp4.error, 'the window/web show that message')

# masking and auto-block guard
check(mod._nm_hp_is_masked('172.18.0.1') and mod._nm_hp_is_masked('192.168.65.1') and not mod._nm_hp_is_masked('192.168.1.50') and not mod._nm_hp_is_masked('8.8.8.8'), 'masked ranges')
blocked = []
mod._nm_firewall_block = lambda ip: (blocked.append(ip) or (True, ''))
mod._NM_HP_AUTOBLOCK['on'] = True
mod._nm_honeypot_autoblock_hook({'ip': '172.18.0.1', 'masked': True}, 5)
mod._nm_honeypot_autoblock_hook({'ip': '203.0.113.9'}, 5)
check(blocked == ['203.0.113.9'], 'auto-block never blocks a Docker gateway address (%s)' % blocked)

# source choice
os.environ['NM_HONEYPOT_SOURCE'] = 'builtin'
check(type(mod._nm_hp_make()).__name__ == '_NMHoneypot', 'prefs/env can bring back the built-in decoys')
os.environ['NM_HONEYPOT_SOURCE'] = 'tpot'
check(type(mod._nm_hp_make()).__name__ == '_NMTpotHoneypot', 'T-Pot is the default source')
del os.environ['NM_HONEYPOT_SOURCE']
check(mod._nm_hp_prefs()['source'] == 'tpot' and mod._nm_hp_prefs()['es'] == 'http://127.0.0.1:64298', 'defaults')


# ── the T-Pot window: status, statistics, recent, control, page ──
import tempfile, json as _json
tdir = tempfile.mkdtemp()
open(os.path.join(tdir, 'docker-compose.yml'), 'w').write('services:\n  a:\n    container_name: cowrie\n  b:\n    container_name: dionaea\n  c:\n    container_name: elasticsearch\n')
open(os.path.join(tdir, '.env'), 'w').write('WEB_USER=abc\nTPOT_X=1\n')
def run_ok(args, cwd=None, timeout=15):
    return 0, 'cowrie|Up 3 minutes\ndionaea|Up 3 minutes (healthy)\nelasticsearch|Up 3 minutes\npihole|Exited (137) 2 months ago\n'
def es_fetch(url, body=None):
    if url.endswith('/_cluster/health'): return {'status': 'green'}
    if url.endswith('/_count'): return {'count': 4261}
    if body and body.get('size') == 0:
        return {'hits': {'total': {'value': 10}}, 'aggregations': {
            'types': {'buckets': [{'key': 'Cowrie', 'doc_count': 5}, {'key': 'Dionaea', 'doc_count': 2}]},
            'ports': {'buckets': [{'key': 22, 'doc_count': 5}]},
            'hist': {'buckets': [{'key': 1792400000000, 'doc_count': 3}, {'key': 1792403600000, 'doc_count': 7}]},
            'pws': {'buckets': [{'key': '123456', 'doc_count': 4}]}}}
    return {'hits': {'hits': [DOCS[0], DOCS[3]]}}
st = mod._nm_tpot_status('http://x', es_fetch, run_ok, tdir)
check(st['state'] == 'running' and st['running'] == 3 and st['expected'] == 3 and st['events'] == 4261 and st['login_set'], 'status: running, only T-Pot containers counted (pihole ignored): %s' % {k: st[k] for k in ('state', 'running', 'expected')})
st2 = mod._nm_tpot_status('http://x', lambda u, b=None: (_ for _ in ()).throw(OSError('x')), lambda a, c=None, t=15: (1, 'no docker'), tdir)
check(st2['state'] == 'docker_off' and not st2['docker'], 'status: Docker not running')
st3 = mod._nm_tpot_status('http://x', lambda u, b=None: (_ for _ in ()).throw(OSError('x')), run_ok, tdir)
check(st3['state'] == 'starting', 'status: containers up but Elasticsearch not answering yet = starting')
sx = mod._nm_tpot_stats('http://x', es_fetch)
check(sx['total'] == 10 and sx['types'][0] == ['Cowrie', 5] and sx['ports'] == [['22', 5]] and len(sx['hist']) == 2 and sx['hist'][0][0] == 1792400000.0 and sx['pws'] == [['123456', 4]] and sx['users'] == [], 'stats parsed')
calls2 = []
def es_flaky(url, body=None):
    calls2.append(1)
    if body and len(body.get('aggs', {})) > 1: raise OSError('400')
    return es_fetch(url, body)
sf = mod._nm_tpot_stats('http://x', es_flaky)
check(sf['types'] and sf['pws'] and len(calls2) > 3, 'one bad field does not blank the page (falls back to one aggregation at a time)')
rc = mod._nm_tpot_recent('http://x', es_fetch, 10)
check(len(rc) == 2 and rc[0]['type'] == 'Cowrie' and rc[0]['sample'] == 'root:123456' and rc[1]['masked'] is True, 'recent events mapped, Docker address masked')
mod._nm_tpot_dir = lambda: tdir
r1 = mod._nm_tpot_control({'action': 'stop'}, local=False)
check(not r1['ok'] and 'this PC' in r1['error'], 'control refuses a request from another device')
seen = []
r2 = mod._nm_tpot_control({'action': 'stop'}, local=True, run=lambda a, c=None, t=15: (seen.append((a, c)) or (0, '')))
check(r2['ok'] and seen[0][0] == ['docker', 'compose', 'stop'] and seen[0][1] == tdir and mod._NM_TPOT_USER_STOP['v'], 'stop runs docker compose stop in the T-Pot folder')
check(not mod._nm_tpot_control({'action': 'wat'}, local=True)['ok'], 'unknown action refused')
# autofeed
mod._NM_TPOT_USER_STOP['v'] = True
check(mod._nm_tpot_autofeed_tick() == 'off', 'autofeed stays off after the user pressed Stop')
mod._NM_TPOT_USER_STOP['v'] = False
class Dummy:
    def __init__(self, **k): self._running = False
    def start(self): self._running = True; return 1
mod._nm_hp_make = lambda **k: Dummy()
mod._NM_HONEYPOT = None
check(mod._nm_tpot_autofeed_tick() == 'started' and mod._nm_tpot_autofeed_tick() == 'running', 'autofeed starts the feed once, then leaves it alone')
# page
class FakeSelf:
    _monitor = None
    def _nm_ai_widget_html(self): return ''
mod._nm_theme_ui = lambda m: {'bg': '#050d1a', 'panel': '#0a1828', 'border': '#1b3550', 'text': '#dbe9f5', 'text2': '#6a9ab8', 'accent': '#38b8f0'}
h = mod._ThreeDServer._build_tpot_html(FakeSelf())
check('<title>T-Pot Honeypot</title>' in h and '@@' not in h and '/api/tpot' in h and '/api/tpot/control' in h, 'page builds, theme tokens filled')
check("'/api/tpot'" in open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read() and "path == '/tpot'" in open(os.path.join(HERE, 'speedtest_monitor.py'), encoding='utf-8').read(), 'routes registered')

print('\nRESULT: ' + ('PASS' if not fails else 'FAIL %d' % len(fails)))
sys.exit(1 if fails else 0)
