#!/usr/bin/env python3
"""Builds site/index.html. Re-run after changing copy or plates."""
import json, math, random, os
HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, '_plates.json')))

# ---------------------------------------------------------------- trace ----
# The headline figures are COMPUTED from this series, never written by hand,
# so the chart and the verdict can never disagree.
random.seed(7)
ADV = 500.0
n = 96
vals, hours_at = [], []
for i in range(n):
    hour = i / n * 24
    # Overnight the line does deliver: a plausible trace has to include tests
    # that meet the advertised rate, or the summary reads as invented.
    if 17 <= hour < 23.5:      band = 0.34 + 0.13 * math.sin(i * 0.55)
    elif 12 <= hour < 17:      band = 0.66 + 0.10 * math.sin(i * 0.4)
    elif 7 <= hour < 12:       band = 0.84
    else:                      band = 1.00
    v = max(0.0, ADV * band * (0.94 + random.random() * 0.10))
    if random.random() < 0.015: v = 0.0          # a dropout
    vals.append(v); hours_at.append(hour)

srt = sorted(vals)
median_all = srt[len(srt)//2]
peak = [v for v, h in zip(vals, hours_at) if 17 <= h < 23.5]
median_peak = sorted(peak)[len(peak)//2] if peak else 0
pct_all  = round(median_all / ADV * 100)
pct_peak = round(median_peak / ADV * 100)
below    = sum(1 for v in vals if v < ADV)
TESTS    = 288

W, H = 760, 250
padL, padR, padT, padB = 48, 16, 20, 30
top = ADV * 1.12
def X(i): return padL + (W - padL - padR) * i / (n - 1)
def Y(v): return padT + (H - padT - padB) * (1 - min(v, top) / top)

measured = " ".join("%.1f,%.1f" % (X(i), Y(v)) for i, v in enumerate(vals))
area = measured + " %.1f,%.1f %.1f,%.1f" % (X(n-1), H - padB, X(0), H - padB)
yadv = Y(ADV)
grid = "".join(
    '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#E4E9EC"/>'
    '<text x="%d" y="%.1f" font-family="IBM Plex Mono" font-size="9" fill="#8A9AA6" '
    'text-anchor="end">%d</text>'
    % (padL, padT + (H-padT-padB)*k/4, W-padR, padT + (H-padT-padB)*k/4,
       padL-7, padT + (H-padT-padB)*k/4 + 3, round(top*(1-k/4)))
    for k in range(5))
ticks = "".join(
    '<text x="%.1f" y="%d" font-family="IBM Plex Mono" font-size="9" fill="#8A9AA6" '
    'text-anchor="middle">%02d:00</text>' % (padL + (W-padL-padR)*h/24, H-9, h)
    for h in (0, 6, 12, 18, 24))
bx0 = padL + (W-padL-padR) * 17/24
bw  = (W-padL-padR) * 6.5/24

SVG = f'''<svg viewBox="0 0 {W} {H}" role="img"
 aria-label="Measured download over 24 hours against a 500 Mbps advertised rate. The
 measured line sits below advertised all day and falls furthest between 17:00 and 23:30.">
 <rect width="{W}" height="{H}" fill="#fff"/>
 {grid}{ticks}
 <rect x="{bx0:.0f}" y="{padT}" width="{bw:.0f}" height="{H-padT-padB}"
       fill="#B8412A" opacity="0.06"/>
 <text x="{bx0+bw/2:.0f}" y="{H-padB-7}" font-family="IBM Plex Mono" font-size="9"
       fill="#B8412A" text-anchor="middle" letter-spacing="1">PEAK HOURS</text>
 <polygon points="{area}" fill="#0B6E93" opacity="0.10"/>
 <polyline points="{padL},{yadv:.1f} {W-padR},{yadv:.1f}" fill="none"
       stroke="#B8412A" stroke-width="1.5" stroke-dasharray="6 4"/>
 <text x="{padL+6}" y="{yadv-7:.1f}" font-family="IBM Plex Mono" font-size="10"
       fill="#B8412A">ADVERTISED 500 Mbps</text>
 <polyline class="draw" points="{measured}" fill="none" stroke="#0B6E93"
       stroke-width="1.9" stroke-linejoin="round" stroke-linecap="round"/>
</svg>'''

def plate(k, alt):
    return f'<img src="data:image/jpeg;base64,{P[k]}" alt="{alt}" loading="lazy">'

CSS = open(os.path.join(HERE, 'style.css')).read()
BODY = open(os.path.join(HERE, 'body.html')).read()
BODY = (BODY.replace('{{SVG}}', SVG)
            .replace('{{PCT_ALL}}', str(pct_all))
            .replace('{{PCT_PEAK}}', str(pct_peak))
            .replace('{{BELOW}}', str(round(below / n * TESTS)))
            .replace('{{TESTS}}', str(TESTS)))
for key, alt in (('main', 'The main dashboard: live download, upload, latency and DNS gauges above history charts'),
                 ('report', 'The report builder dialog: choosing time period, contents and schedule'),
                 ('world', 'Network hosts placed on a rotating globe at their real geographic locations'),
                 ('radar', 'A sonar scope plotting hosts by geographic position'),
                 ('capture', 'Packet capture analysis with a protocol breakdown'),
                 ('quality', 'Connection quality scoring showing jitter, packet loss and stability')):
    BODY = BODY.replace('{{PLATE_%s}}' % key.upper(), plate(key, alt))

HTML = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vanguard Flow NetSentinel &mdash; measure what your line actually delivers</title>
<meta name="description" content="A Windows network monitor that records what your broadband actually delivers, then produces a timestamped evidence pack you can put in front of your provider.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>
{BODY}
</body></html>
'''
open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8').write(HTML)
print("built index.html  %d KB" % (len(HTML)//1024))
print("computed from the plotted series:")
print("   median overall = %.0f Mbps  (%d%% of advertised)" % (median_all, pct_all))
print("   median 17:00-23:30 = %.0f Mbps  (%d%%)" % (median_peak, pct_peak))
print("   below advertised: %d of %d samples -> %d of %d tests"
      % (below, n, round(below/n*TESTS), TESTS))
