# Vanguard Flow NetSentinel

A real-time network monitoring, packet-capture, and threat-detection desktop app with a built-in web dashboard, 3D topology visualizer, honeypot, and local AI analysis — all in one Python application, no cloud account required.

It runs on Windows (with a full installer) and Linux (packaged as `.deb` or AppImage) from the same source file.

## Screenshots

| | |
|---|---|
| ![Main screen](docs/screenshots/main%20screen.jpg) | ![3D view](docs/screenshots/etherape%203d%20view.jpg) |
| ![Sankey flow map](docs/screenshots/etherape%20sankey%20view.jpg) | ![Wireshark monitor](docs/screenshots/wireshark%20monitor.jpg) |
| ![Top talkers with radar](docs/screenshots/etherape%20top%20tallkers%20with%20radar.jpg) | ![Radial view](docs/screenshots/etherape%20radial%20view.jpg) |

More in [`docs/screenshots/`](docs/screenshots/): geo map, heatmap, network quality, evidence pack, Wireshark IDS/capture analysis, settings, tools, and the kill-switch button.

## What it does

Vanguard Flow NetSentinel started as a speed-test monitor and grew into a full local network-operations console: it measures your connection, captures and visualizes your traffic, watches for scanners and intrusions, and can explain what it's seeing in plain language via a locally-running AI — all served from a single Python process, viewable in-app (Tkinter desktop windows) or from any browser on your network (built-in web server + optional standalone remote client).

## Features

### Speed & connection quality

- **Multi-engine speed testing** — auto-detects and uses whichever CLI is available: `librespeed-cli` (LGPL), `speedtest-cli` (Apache), or Ookla's own CLI if you already have it. Ookla's CLI is never bundled or auto-installed (its license forbids redistribution); the installer fetches `librespeed-cli` instead. Runs automatically every 5 minutes (configurable) or on demand, tracking up to 10,000 readings.
- **Bufferbloat grading (A+ to F)** — pings continuously while a speed test saturates the link and grades the added latency, so you can see whether your connection falls apart under load, not just how fast it is at rest.
- **DNS monitoring** — resolves six well-known hosts (google.com, cloudflare.com, microsoft.com, amazon.com, bbc.co.uk, github.com), timed and averaged, alongside every speed test.
- **Time-of-day heatmap** — a 7×24 grid of download/upload/ping/DNS medians by weekday and hour, so patterns like "evenings are always slow" jump out visually.
- **Outage detection** — flags gaps in successful tests as discrete outages with start/end/duration, feeding both a dedicated Outages window and the evidence pack below.
- **VDI session health** — detects active Blast Extreme, PCoIP, and RDP sessions on the machine, pings the remote host for RTT/loss, and grades each session good/fair/poor — useful for diagnosing "my remote desktop feels laggy" in real time.
- **ISP Evidence Pack** — a one-click, eight-page PDF report (measurement window, uptime %, outage log, percentiles vs. your advertised speed, peak-vs-off-peak comparison, daily breakdown) built specifically to hand to an ISP instead of arguing over screenshots.

### Packet capture & traffic visualization

- **Wireshark Monitor** — a full `tshark`-backed capture window: live color-coded packet list, Wireshark-syntax display filters, right-click quick filters and Follow Stream, protocol/hex detail panes, and the standard Statistics/Analyze menus (Conversations, Endpoints, I/O Graph, Expert Information, Decode As). Open/save PCAP and PCAPNG files directly.
- **EtherApe-style topology view** — a live force-graph of hosts and flows: node size and line thickness scale with traffic volume, colors track protocol, animated pulses show direction. Protocol filtering, DNS resolution, adjustable fonts, and PCAP replay at up to 16× speed.
- **Timeline scrubber** — both the desktop topology view and the web Top Talkers page buffer recent snapshots so you can rewind and replay recent traffic without stopping the live capture.
- **3D network visualization** (`/3d`) — a rotating WebGL view of your network: a starfield-and-glass-wall room, hosts and flows in 3D space, scrolling neon protocol-traffic bars, a wall-mounted live packet console, and a toggleable reference grid. Includes buttons for a kill switch, an attack simulation, and a rotating **World View** that wraps the topology onto a globe with a real day/night terminator.
- **Sonar Radar & Threat Radar** — hosts plotted at their real geographic location on a sonar-style scope, with an audible ping on genuinely new connections; the Threat Radar shows only hostile/suspicious hosts with country flags and severity-based pulsing.
- **Flow Map (Sankey)** — a full-width traffic-flow diagram using true alpha-blended gradient ribbons, with live Active Hosts / Active Flows / Flow Detail panels.
- **Top Talkers** — a live-ranked web table of your busiest hosts with WHOIS org/country, dominant protocol, and traffic share.
- **Device/vendor identification** — a built-in MAC-prefix vendor table (Apple, Amazon, Google, Microsoft, TP-Link, Raspberry Pi, and more) labels devices in your inventory automatically.

### Security & threat detection

- **Honeypot with tarpit** — binds 19 TCP and 10 UDP decoy ports mimicking SSH, RDP, SMB, databases, Docker's API, and industrial control protocols. Connections are fingerprinted against ~28 known scanner/tool signatures and logged. TCP decoys are held open and drip-fed data for up to 10 minutes instead of closing immediately, wasting a scanner's time; UDP decoys never reply at all, so the honeypot can't be abused as a reflection amplifier. Sweep and volume alerts fire automatically, with an optional auto-block-after-2-hits toggle.
- **Firewall management** — blocks and unblocks hosts directly through the OS firewall (Windows `netsh`, Linux `nftables` in the app's own isolated table), with a searchable rules window and live-read state so it never drifts from what's actually blocked.
- **Kill switch** — one button blocks all inbound/outbound traffic on the machine while leaving the local dashboard on `127.0.0.1` reachable to turn it back off.
- **Country (geo) firewall blocking** — block every currently-known IP from a given country and auto-block any newly-seen IP from that country going forward.
- **Threat-intel feeds** — downloads and caches public IP/CIDR blocklists (Emerging Threats, Feodo Tracker, ET Compromised IPs) plus any feeds you add, and matches live traffic against them.
- **ML-based flow anomaly detection** — a local Isolation Forest model (scikit-learn) flags statistically unusual flows, no cloud dependency, and no-ops gracefully if scikit-learn isn't installed.
- **Attack Drill** — simulates realistic-looking hostile traffic from cities worldwide, using only IANA documentation/example IP ranges so it can never touch or block a real host, to demonstrate what a genuine detection and block looks like.

### AI-powered analysis (local by default)

- **Runs on Ollama by default, no API key needed** — the app starts Ollama automatically on launch. Anthropic's API is available as an alternate provider if you switch to it in Settings, but it's optional.
- **Capture analysis** — quick prompts (summarize, find suspicious patterns, top hosts, DNS lookups, errors) or free-text questions against the current packet capture, without stopping it.
- **Report builder** — turn AI answers into a self-contained HTML report you can print to PDF, no internet required to view it later.
- **Continuous flow-watch** — a background loop re-analyzes live traffic roughly every 30 seconds for behavioral, traffic, and IDS-style findings.
- **Daily AI briefing** — a plain-language daily summary of speed, uptime, alerts, new devices, and top talkers.

### Remote access & multi-machine monitoring

- **Remote Agents** — lightweight headless scripts you deploy on other machines that run their own speed tests and DNS checks and expose a small HTTP API; the main app polls and folds their data into the dashboard.
- **Standalone remote client** (`nm_client.py`) — a separate Tkinter app that talks only to the documented HTTP API, so it works from anywhere on the network: dashboard, alerts, devices, latency, quality, heatmap, outages, VDI, flow map, honeypot, firewall, agents, and analytics tabs, plus links out to the browser for the heavier WebGL/HTML views. Requires a license key by default (a local Settings toggle can disable that requirement); the browser dashboard itself is never gated.
- **Web dashboard / PWA** — the built-in server serves a mobile-friendly dashboard installable as a Progressive Web App with offline app-shell caching.
- **Cross-platform** — the same single file runs on Linux (`nftables` firewall backend, libpcap/tshark capture, `.deb`/AppImage packaging) as well as Windows.

### Alerting & reporting

- **Threshold-based alerts** — independently configurable thresholds for download/upload/ping/jitter/loss/bufferbloat, debounced to avoid spam, plus alerts for honeypot activity, poor VDI sessions, new devices, kill-switch state, and firewall changes.
- **Notification backends** — Pushover, a generic webhook, ntfy, or a Windows desktop toast.
- **Scheduled reports** — generate reports on demand or on an hourly/daily/weekly schedule, with a report viewer to browse everything previously generated.
- **CSV/JSON export** — export any date range of speed-test history in either format.

### Platform & UX

- **Five built-in color themes** plus custom per-metric color overrides.
- **Embedded terminal/SSH tool** (MobaXterm-hosted) so you don't have to leave the app for a quick session.
- **Pi-hole integration** — a direct link to a Pi-hole admin UI running alongside the monitor.
- **Database hygiene tools** — a one-click "purge corrupt speed readings" cleanup that backs up the database first and only clears the affected fields.
- **SQLite-backed storage** by default (with a JSON fallback), so history survives restarts without any setup.

## Requirements

- **Windows**: Windows 10 or later (64-bit). The installer downloads and installs Wireshark + Npcap, Ollama, and a speed-test CLI directly from each project's own site at install time — nothing third-party is bundled. Run as Administrator for packet capture and firewall features.
- **Linux**: any recent distro; packet capture needs the `wireshark` group, firewall/kill-switch features need root, everything else runs unprivileged.

## Installation

**Windows**: run `NetworkMonitorSetup.exe` (built from `installer.nsi` — see [Building from source](#building-from-source)). Choose the "Full" preset for the monitor app plus capture/AI components, or "Client only" to install just `nm_client.py` on a second machine.

**Linux**: build a `.deb` with `./build-linux.sh deb` and install it with `apt install ./netsentinel_1.0.0_all.deb` (not raw `dpkg -i`, so dependencies resolve correctly), or build a portable AppImage with `./build-linux.sh appimage`.

## Usage

Launch from the Desktop/Start Menu shortcut, or run `speedtest_monitor.py` directly with Python. The web dashboard is served on `http://localhost:8765` by default. Right-click and "Run as Administrator" (Windows) or ensure your user is in the `wireshark` group (Linux) for full packet-capture functionality.

## Building from source

| File | Purpose |
|---|---|
| `speedtest_monitor.py` | Main application — desktop UI, web server, capture engine, everything |
| `nm_client.py` | Standalone remote client |
| `build.bat` / `build-linux.sh` | Build scripts (PyInstaller-based) |
| `installer.nsi` / `build_installer.bat` | Windows installer (NSIS, no third-party plugins required) |
| `web/`, `website/` | Source for the embedded web UI and the project landing page |
| `selftest.py` / `selftest_golden.json` | Regression test suite — run before and after any change |
| `requirements.txt` | Python dependencies |

See [`BUILD_NOTES.txt`](BUILD_NOTES.txt) for full build details, and [`CHANGES_this_session.md`](CHANGES_this_session.md) for a detailed log of recent changes.

## License

See [`LICENSE.txt`](LICENSE.txt).
