Vanguard Flow NetSentinel v1.0
====================

A real-time network monitoring tool with:
  - Live speed test gauges
  - DNS monitoring
  - Wireshark packet capture frontend
  - EtherApe network topology visualiser
  - Optional remote client (connects to this or another PC)
  - AI-powered capture analysis (local, via Ollama — no API key)
  - "System" button opens Task Manager TMOG, the real system
    monitor app (bundled and installed alongside this app)
  - WSL + Kali Linux installed for pen testing your own network
  - "Pen Test" button opens an Nmap scanner with an AI assistant
    that can craft scans and recommend next steps

Requirements:
  - Windows 10 version 2004 (build 19041) or later, or Windows 11
    (older Windows 10 still runs the app, just without WSL/Kali)
  - Wireshark (silent) + Npcap (one short wizard to click)
  - Nmap (silent — installed by the installer)
  - Ollama (local AI engine — installed by the build script)
  - Run as Administrator for packet capture

WSL + Kali Linux:
  Installed via `wsl --install -d kali-linux` — Kali's own official
  WSL install method. A brand-new WSL install commonly needs ONE
  restart before Kali is ready; the installer tells you if so.
  After that (or right away if WSL was already set up), open a
  Command Prompt and run once:
    wsl -d kali-linux
  to finish Kali's own first-time setup (it asks you to create a
  UNIX username and password — that's Kali's own step, not this
  installer's). The "Pen Test" button in the app itself now opens
  a Kali desktop directly via Win-KeX, once that first-time setup
  is done.

Pen Test (Nmap scanner):
  The app's "Pen Test" button opens an Nmap scan builder: pick a
  target and a scan profile (or describe what you want in plain
  English and let the built-in AI craft the flags), watch the scan
  run live, then ask the AI to recommend next steps from the
  results. A "Kali Desktop ^(Win-KeX^)" button in that same window
  still opens the Kali desktop directly, same as before.
  Only scan hosts and networks you own or have explicit permission
  to test.

AI features:
  The app runs its AI locally through Ollama and starts it
  automatically on launch. Pull a model once with, e.g.:
    ollama pull llama3.2
  No Anthropic API key is required.

Usage:
  Launch from Desktop or Start Menu shortcut.
  Right-click and select "Run as Administrator" for
  full packet capture functionality.

Wireshark / Npcap:
  Packet capture requires the Npcap driver. The free build of
  Npcap cannot be installed silently (that is a paid OEM
  feature), so the installer opens its short wizard - just
  click through with the defaults. Wireshark itself installs
  silently, and Npcap is skipped entirely if already present.
  Nmap (for the "Pen Test" button) installs silently right after,
  reusing that same Npcap install rather than bringing its own.
  If capture fails, try running as Administrator.
