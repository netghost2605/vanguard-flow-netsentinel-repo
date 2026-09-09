# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for speedtest_agent — the small headless agent that the
# main app's "Push Agent" feature deploys onto remote Windows/Linux boxes.
#
# Unlike nm_client.spec (which produces a whole dist/nm_client/ folder via
# COLLECT), this builds a single onefile exe/binary on purpose: Push Agent
# copies exactly one file to the target machine, so a folder full of loose
# DLLs would just be extra transfer/deployment complexity for no benefit.
# Same onefile style as speedtest_monitor.spec.
#
# Run:  pyinstaller speedtest_agent.spec
# Produces: dist/SpeedtestAgent.exe (Windows) or dist/SpeedtestAgent (Linux)

from pathlib import Path

HERE = Path(SPECPATH)

a = Analysis(
    [str(HERE / 'speedtest_agent.py')],
    pathex=[str(HERE)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The agent is pure stdlib (argparse/http.server/threading/socket/
    # subprocess) — none of the main app's heavy deps (numpy, matplotlib,
    # Pillow, reportlab...) are imported by it, so excluding them keeps this
    # exe small and the build fast rather than dragging in the whole app's
    # dependency set by accident.
    excludes=['scipy', 'pandas', 'numpy', 'matplotlib', 'mpl_toolkits',
              'PIL', 'reportlab', 'IPython', 'jupyter'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SpeedtestAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # headless — prints status/log lines, must stay a console app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
