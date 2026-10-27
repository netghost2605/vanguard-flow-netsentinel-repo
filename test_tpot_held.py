#!/usr/bin/env python3
"""Honeytrap records in the Honeypot window: the bytes the visitor sent are shown, and the time each connection was
held is counted. Shapes below are the real ones read from the T-Pot VM (attack_connection.payload.data_hex,
start_time / end_time). Run: python3 test_tpot_held.py"""
import importlib.util, os, sys, time, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['NM_WIFI_TEST'] = '1'
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def z(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
now = time.time()
get = b'GET / HTTP/1.1\r\nHost: 1.2.3.4:80\r\n\r\n'
bt = b'\x13BitTorrent protocol' + b'\x00' * 8
def doc(i, ip, port, start, end, data):
    return {'_id': i, '_source': {'@timestamp': iso(start), 'type': 'Honeytrap', 'src_ip': ip, 'dest_port': str(port),
            'start_time': z(start), 'end_time': z(end),
            'attack_connection': {'protocol': 'tcp', 'payload': {'data_hex': data.hex(), 'length': str(len(data)), 'md5_hash': 'x'}}}}
DOCS = [doc('h1', '203.0.113.5', 27976, now - 100, now - 89, get),            # ended 89 s ago, held 11 s
        doc('h2', '203.0.113.6', 8888, now - 30, now - 20, bt),                # held 10 s, ended 20 s ago
        doc('h3', '203.0.113.7', 9006, now - 15, now - 3, get),                # held 12 s, ended 3 s ago
        {'_id': 'h4', '_source': {'@timestamp': iso(now - 5), 'type': 'Honeytrap', 'src_ip': '203.0.113.8', 'dest_port': '23'}}]  # no payload, no times
def fake(url, body=None):
    if url.endswith('/_cluster/health'): return {'status': 'green'}
    since = body['query']['bool']['filter'][0]['range']['@timestamp']['gte']
    return {'hits': {'hits': [d for d in DOCS if d['_source']['@timestamp'] >= since]}}
hp = mod._NMTpotHoneypot(fetch=fake, cursor_load=lambda: None, cursor_save=lambda t: None)
hp._ts = now - 3600
n = hp.poll()
H = {h['ip']: h for h in hp.hits()}
check(n == 4, 'all four Honeytrap events filed (%d)' % n)
check(H['203.0.113.5']['sample'].startswith('GET / HTTP/1.1'), '"First bytes" shows what the visitor sent: %r' % H['203.0.113.5']['sample'][:30])
check(H['203.0.113.5']['tool'] != '', '"Looks like" is filled in from those bytes: %r' % H['203.0.113.5']['tool'])
check('BitTorrent' in H['203.0.113.6']['sample'], 'a binary handshake is shown too')
check(H['203.0.113.8']['sample'] == '' and H['203.0.113.8']['tool'] == '', 'a record with no payload stays blank (no crash)')
sm = hp.summary()
check(sm['held_n'] == 3, 'three connections counted as held (%d)' % sm['held_n'])
check(abs(sm['held_secs'] - 33.0) < 1.5, 'total scanner time held is 11+10+12 s (%.1f)' % sm['held_secs'])
check(sm['held_recent'] == 2, 'the two that ended in the last minute count as recent, the one from 89 s ago does not (%d)' % sm['held_recent'])
check(sm['tarpit_active'] == 0 and sm['tarpit_enabled'] is False, 'the old "stuck now" counter is untouched')
# second poll files nothing twice, totals do not grow
hp.poll()
check(hp.summary()['held_n'] == 3, 'nothing is counted twice on the next poll')
# bad data never raises
bad = {'_source': {'attack_connection': {'payload': {'data_hex': 'zz1'}}, 'start_time': 'nope', 'end_time': None}}
check(mod._NMTpotHoneypot._payload_bytes(bad['_source']) == b'', 'bad hex gives no bytes')
hp._note_held(bad['_source'])
check(hp.summary()['held_n'] == 3, 'bad times are ignored')
check(mod._NMTpotHoneypot._sample_any({'type': 'Cowrie', 'username': 'a', 'password': 'b'}) == 'a:b', 'other event types keep their own sample')
print('\nRESULT: PASS' if not fails else '\nRESULT: FAIL %d' % len(fails))
sys.exit(1 if fails else 0)
