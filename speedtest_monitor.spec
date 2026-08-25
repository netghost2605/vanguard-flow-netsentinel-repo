# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for speedtest_monitor
# Run:  pyinstaller speedtest_monitor.spec
# Or just double-click build.bat
#
# Requirements:
#   - speedtest.exe must be in the same folder as this .spec file before building
#   - pip install pyinstaller numpy matplotlib mplcursors
#

import sys
from pathlib import Path

HERE = Path(SPECPATH)

# ── Collect all matplotlib / numpy data files automatically ───────────────
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
datas += collect_data_files('matplotlib')
datas += collect_data_files('mpl_toolkits')
datas += collect_data_files('PIL')
datas += collect_data_files('reportlab')

# ── Bundle speedtest.exe next to the script ───────────────────────────────
speedtest_exe = HERE / 'speedtest.exe'
if speedtest_exe.exists():
    datas.append((str(speedtest_exe), '.'))
else:
    import warnings
    warnings.warn(
        "\n\n  WARNING: speedtest.exe not found in the build folder.\n"
        "  Copy speedtest.exe here before building, otherwise the\n"
        "  packaged app will not be able to run speed tests.\n",
        stacklevel=2
    )

# ── Bundle background image ────────────────────────────────────────────────
bg_img = HERE / 'bg.jpg'
if bg_img.exists():
    datas.append((str(bg_img), '.'))
else:
    import warnings
    warnings.warn(
        "\n\n  WARNING: bg.jpg not found in the build folder.\n"
        "  The app will fall back to a plain dark background.\n",
        stacklevel=2
    )

# ── Hidden imports that PyInstaller sometimes misses ─────────────────────
hiddenimports = [
    'mplcursors',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_agg',
    'tkinter',
    'tkinter.colorchooser',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.ttk',
    'numpy',
    'numpy.core._multiarray_umath',
    'numpy.core._multiarray_tests',
    'pkg_resources.py2_compat',
    # Pillow – required by matplotlib.colors at import time
    'PIL',
    'PIL.Image',
    'PIL.BmpImagePlugin',
    'PIL.PngImagePlugin',
    'PIL.JpegImagePlugin',
    'PIL.GifImagePlugin',
    'PIL.TiffImagePlugin',
    'PIL.WebPImagePlugin',
    'PIL.PpmImagePlugin',
    'PIL._imaging',
    # reportlab – required for PDF report generation
    'reportlab',
    'reportlab.platypus',
    'reportlab.platypus.flowables',
    'reportlab.platypus.doctemplate',
    'reportlab.platypus.tables',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.styles',
    'reportlab.lib.units',
    'reportlab.lib.colors',
    'reportlab.lib.enums',
    'reportlab.lib.utils',
    'reportlab.pdfgen',
    'reportlab.pdfgen.canvas',
    'reportlab.pdfbase',
    'reportlab.pdfbase.pdfmetrics',
    'reportlab.pdfbase.ttfonts',
    'reportlab.graphics',
]

a = Analysis(
    [str(HERE / 'speedtest_monitor.py')],
    pathex=[str(HERE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'scipy', 'pandas',          # slim the bundle
        'IPython', 'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SpeedtestMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,          # compress if UPX is available (optional)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,      # keep True to see error output if something goes wrong
                       # change to False once you're happy with it
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # uncomment and provide an .ico file to set a custom icon
)
