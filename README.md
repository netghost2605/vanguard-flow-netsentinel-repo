# Vanguard Flow NetSentinel

A real-time network monitoring tool for Windows with:

- Live speed test gauges
- DNS monitoring
- Wireshark packet capture front-end
- EtherApe-style network topology visualizer (2D and 3D views)
- Optional remote client (connects to this or another PC)
- AI-powered capture analysis (local, via Ollama — no API key required)
- A honeypot/decoy system for detecting scanners and attackers

## Screenshots

| | |
|---|---|
| ![Main screen](docs/screenshots/main%20screen.jpg) | ![3D view](docs/screenshots/etherape%203d%20view.jpg) |
| ![Sankey view](docs/screenshots/etherape%20sankey%20view.jpg) | ![Wireshark monitor](docs/screenshots/wireshark%20monitor.jpg) |

More screenshots are in [`docs/screenshots/`](docs/screenshots/).

## Requirements

- Windows 10 or later (64-bit)
- Wireshark + Npcap (the installer handles Wireshark silently; Npcap needs one short wizard click-through unless already present)
- Ollama (local AI engine) for the AI-powered capture analysis feature
- Run as Administrator for packet capture

## AI features

The app runs its AI features locally through Ollama and starts it automatically on launch. Pull a model once, e.g.:

```
ollama pull llama3.2
```

No API key is required.

## Usage

Launch from the Desktop or Start Menu shortcut. Right-click and choose "Run as Administrator" for full packet capture functionality.

## Building from source

- `speedtest_monitor.py` — main application
- `nm_client.py` — remote client
- `build.bat` / `build-linux.sh` — build scripts
- `installer.nsi` / `build_installer.bat` — Windows installer (NSIS)
- `web/`, `website/` — source for the embedded web UI and project landing page
- `selftest.py` / `selftest_golden.json` — regression test suite

See `BUILD_NOTES.txt` for build details.

## License

See [`LICENSE.txt`](LICENSE.txt).
