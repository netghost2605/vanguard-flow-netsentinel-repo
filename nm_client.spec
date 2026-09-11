# -*- mode: python ; coding: utf-8 -*-
#
# NOTE: this .spec is not what build_installer.bat actually builds with --
# it invokes PyInstaller with plain CLI flags instead (--onefile --windowed
# --collect-data matplotlib ...). Kept in sync anyway in case this is ever
# run directly (`pyinstaller nm_client.spec`), so it doesn't quietly ship
# the same "charts silently fall back to text" bug that CLI build had
# before --collect-data was added there.

from PyInstaller.utils.hooks import collect_data_files

# nm_client.py imports matplotlib lazily (inside a try/except around each
# chart draw), so PyInstaller's import scan finds and bundles the package
# itself without help -- but its own data directory (mpl-data: fonts,
# style sheets, backend registry) is NOT picked up automatically. Without
# it, `import matplotlib` succeeds and then blows up moments later inside
# matplotlib's own init -- caught by nm_client's try/except, so every
# chart (Dashboard/Latency/Quality) silently falls back to a plain text
# table with no visible error. Same fix speedtest_monitor.spec already
# applies for the same reason.
datas = collect_data_files('matplotlib')

hiddenimports = [
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_agg',
    'numpy',
    'numpy.core._multiarray_umath',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
]

a = Analysis(
    ['nm_client.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='nm_client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nm_client',
)
