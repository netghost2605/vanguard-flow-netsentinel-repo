Vanguard Flow NetSentinel v1.0
====================

A real-time network monitoring tool with:
  - Live speed test gauges
  - DNS monitoring
  - Wireshark packet capture frontend
  - EtherApe network topology visualiser
  - Optional remote client (connects to this or another PC)
  - AI-powered capture analysis (local, via Ollama — no API key)

Requirements:
  - Windows 10 or later (64-bit)
  - Wireshark (silent) + Npcap (one short wizard to click)
  - Ollama (local AI engine — installed by the build script)
  - Run as Administrator for packet capture

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
  Nmap is NOT required and is no longer installed.
  If capture fails, try running as Administrator.
