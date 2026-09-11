@echo off
setlocal EnableDelayedExpansion
title Vanguard Flow NetSentinel — Build Installer
color 0A

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║       Vanguard Flow NetSentinel — Full Installer Build         ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ── Check we're in the right folder ──────────────────────────────────────────
if not exist "speedtest_monitor.py" (
    echo  [ERROR] speedtest_monitor.py not found.
    echo  Run this script from the project folder.
    pause & exit /b 1
)
:: A speed-test CLI is NOT bundled in this build folder. Ookla's licence
:: restricts redistribution, so that one is never bundled or auto-installed.
:: librespeed-cli (LGPL) IS auto-installed for the end user, but by
:: installer.nsi at install time (see its SecSpeedtest section) - not by
:: anything in this build script, so there is nothing to check for here.
if not exist "speedtest.exe" (
    echo  [INFO] No speedtest.exe here - fine, it is not bundled.
    echo         The installer fetches librespeed-cli automatically instead.
)

:: Task Manager TMOG (real system-monitor app) - unlike Wireshark/Npcap/
:: Ollama/librespeed-cli, this one IS bundled directly (not downloaded at
:: install time), because there is no stable public silent-download URL
:: for it. installer.nsi embeds it and installs it silently; the app's
:: "System" button launches the real installed exe. Missing here just
:: means installer.nsi's own !if /FileExists guard skips that section
:: cleanly - not a build failure.
if not exist "TMOGTaskManagerSetup.exe" (
    echo  [WARN] TMOGTaskManagerSetup.exe not found - the installer will skip
    echo         bundling Task Manager TMOG, and the app's System button will
    echo         show its own "not found" message until it is installed some
    echo         other way. Put TMOGTaskManagerSetup.exe in this folder to
    echo         include it.
) else (
    echo  [OK] TMOGTaskManagerSetup.exe found - will be bundled and installed.
)

:: WSL + Kali Linux (pen testing environment) - nothing to bundle here. Unlike
:: TMOG above, Kali has no installer file of its own to include: installer.nsi
:: runs `wsl --install -d kali-linux`, which fetches the Kali image itself
:: straight from Microsoft's own distribution at install time on the end
:: user's machine. So there is nothing for this build script to check for.
echo  [INFO] Task Manager TMOG's "System" button aside, the installer also
echo         sets up WSL + Kali Linux (a pen-testing environment) - it
echo         downloads Kali itself at install time, nothing bundled here.

:: ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found on PATH.
    echo  Install Python 3.10+ from https://www.python.org/
    pause & exit /b 1
)
echo  [OK] Python found.

:: ── Check / bootstrap pip ─────────────────────────────────────────────────────
:: Some Python installs (a minimal/custom install, or one where pip got
:: removed) have no "pip" module at all -- "python -m pip install X" then
:: fails immediately with "No module named pip", before it ever gets a
:: chance to install anything. This is a real, seen-in-the-wild failure
:: mode (not the PATH-mismatch one above -- this is the SAME python that
:: PyInstaller will use, it just plain doesn't have pip). ensurepip
:: bootstraps pip from the copy the Python standard library already
:: ships, no network needed for this step.
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] pip missing for this Python -- bootstrapping via ensurepip...
    python -m ensurepip --upgrade
    python -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] Still no pip after ensurepip. Find out which Python is
        echo          really on PATH and reinstall/repair it:
        echo              python -c "import sys; print(sys.executable)"
        echo          then reinstall that Python from python.org with
        echo          "pip" checked during setup.
        pause & exit /b 1
    )
)
echo  [OK] pip ready.

:: ── Check / install PyInstaller ───────────────────────────────────────────────
:: Everything below uses "python -m pip" / "python -m PyInstaller" rather than
:: bare "pip" / "pyinstaller" commands. On a machine with more than one Python
:: on PATH, bare "pip" and bare "pyinstaller" are separate .exe shims that can
:: silently resolve to a DIFFERENT install than bare "python" -- which is
:: exactly how you get pip reporting a clean install while the exe that
:: PyInstaller builds a moment later has never heard of the package: it was
:: installed into one Python's site-packages while PyInstaller ran out of
:: another's. Routing everything through the one "python" already checked
:: above removes that whole class of bug.
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo  Installing PyInstaller...
    python -m pip install pyinstaller --quiet
)
echo  [OK] PyInstaller ready.

:: ── Check / install Python dependencies ──────────────────────────────────────
echo  Installing Python dependencies...
python -m pip install numpy matplotlib mplcursors Pillow --quiet
:: nvidia-ml-py (imported as "pynvml") gives the System Monitor real NVIDIA
:: GPU readings — name, utilization, memory, power, temperature, clock — via
:: NVML. It is pure Python (no compiled extension), so bundling it here means
:: PyInstaller's own import scan of speedtest_monitor.py picks it up and
:: freezes it into SpeedtestMonitor.exe automatically; nothing else to wire
:: up. It's a no-op on a machine with no NVIDIA GPU/driver — the app already
:: catches that ImportError/NVMLError itself and shows "Unavailable" with the
:: real reason, never a fabricated reading. Installed here (build time) so it
:: ships INSIDE the exe; end users never need to pip install anything.
python -m pip install nvidia-ml-py --quiet
:: paramiko (SSH) + pywinrm (PowerShell Remoting) power the Push Agent
:: feature — deploying speedtest_agent onto a remote Windows/Linux box.
:: Both are pure Python plus small compiled deps PyInstaller already knows
:: how to bundle (cryptography for paramiko), so this is the same
:: "installed at build time, ships inside the exe" pattern as everything
:: else in this block.
python -m pip install paramiko pywinrm --quiet
:: Verify THIS python (the one about to run PyInstaller below) can actually
:: import them, instead of trusting a silent pip "success" -- catches the
:: exact "installed but into the wrong Python" failure mode described above
:: before it wastes another build+test cycle.
python -c "import paramiko, winrm" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] paramiko/pywinrm did not install where "python" can see them.
    echo          Find out which Python is actually on PATH and use it explicitly:
    echo              python -c "import sys; print(sys.executable)"
    echo              python -m pip install paramiko pywinrm
    echo          Push Agent's build will fail to include them until this
    echo          import succeeds under the same "python" used below.
    pause
    exit /b 1
)
echo  [OK] Python dependencies installed (including nvidia-ml-py for GPU readings,
echo       paramiko + pywinrm for Push Agent).

:: ── Check / install Ollama (local AI engine) ─────────────────────────────────
::    The app runs its AI locally via Ollama (no API key). Make sure it's present
::    on this machine; if not, download and silently install the official build.
echo.
echo  Checking for Ollama (local AI engine)...
set "OLLAMA_EXE="
for /f "delims=" %%i in ('where ollama 2^>nul') do set "OLLAMA_EXE=%%i"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"

if defined OLLAMA_EXE (
    echo  [OK] Ollama already installed: !OLLAMA_EXE!
) else (
    echo  [..] Ollama not found — downloading the official installer ^(~5 MB^)...
    set "OLLAMA_SETUP=%TEMP%\OllamaSetup.exe"
    if exist "!OLLAMA_SETUP!" del "!OLLAMA_SETUP!" >nul 2>&1

    :: Prefer curl (built into Windows 10 1803+); fall back to PowerShell.
    curl -L --fail --silent --show-error -o "!OLLAMA_SETUP!" https://ollama.com/download/OllamaSetup.exe
    if errorlevel 1 (
        echo  [..] curl unavailable/failed — trying PowerShell...
        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "try { Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '!OLLAMA_SETUP!' -UseBasicParsing } catch { exit 1 }"
    )

    if not exist "!OLLAMA_SETUP!" (
        echo  [WARN] Could not download Ollama. The build will continue, but the
        echo         app's AI features need Ollama. Install it later from:
        echo         https://ollama.com/download/windows
    ) else (
        echo  [..] Installing Ollama silently...
        start /wait "" "!OLLAMA_SETUP!" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
        del "!OLLAMA_SETUP!" >nul 2>&1
        set "OLLAMA_EXE="
        for /f "delims=" %%i in ('where ollama 2^>nul') do set "OLLAMA_EXE=%%i"
        if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
        if defined OLLAMA_EXE (
            echo  [OK] Ollama installed.
        ) else (
            echo  [WARN] Ollama install did not complete as expected. Install it
            echo         manually from https://ollama.com/download/windows
        )
    )
)

:: ── Optional: nudge about the AI model, without stopping the build for input ──
:: This used to be a blocking `choice` prompt every single run asking whether
:: to pull llama3.2 - annoying once you already have a model pulled, which is
:: the common case after the first build. Now it only speaks up when Ollama
:: genuinely has zero models pulled, and it never blocks waiting for a keypress
:: or auto-downloads anything on its own.
if defined OLLAMA_EXE (
    set "OLLAMA_HAS_MODEL="
    for /f "skip=1 delims=" %%m in ('"!OLLAMA_EXE!" list 2^>nul') do set "OLLAMA_HAS_MODEL=1"
    if not defined OLLAMA_HAS_MODEL (
        echo.
        echo  [i]  No Ollama model pulled yet - the app's AI features need one.
        echo       Pull the default anytime with:  ollama pull llama3.2
    )
)

:: ── Check NSIS ────────────────────────────────────────────────────────────────
set "NSIS_PATH="
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set "NSIS_PATH=C:\Program Files (x86)\NSIS\makensis.exe"
if exist "C:\Program Files\NSIS\makensis.exe" set "NSIS_PATH=C:\Program Files\NSIS\makensis.exe"

if "!NSIS_PATH!"=="" (
    echo.
    echo  [ERROR] NSIS not found.
    echo  Download and install NSIS from: https://nsis.sourceforge.io/Download
    echo.
    echo  After installing NSIS, re-run this script.
    pause & exit /b 1
)
echo  [OK] NSIS found.
:: NOTE: installer.nsi no longer needs any third-party NSIS plugin (no more
:: inetc dependency - its downloads now go through a generated PowerShell
:: script + stock ExecWait instead). A prior version of this script tried
:: to auto-install the inetc plugin here; that step is gone because the
:: thing it was installing is no longer used at all.

:: Branding assets: welcome.bmp (164x314) + header.bmp (150x57) give the
:: installer its branded look. installer.nsi skips them gracefully if absent.
if not exist "welcome.bmp" echo  [WARN] welcome.bmp missing - plain MUI sidebar will be used.
if not exist "header.bmp"  echo  [WARN] header.bmp missing - plain MUI header will be used.
if exist "welcome.bmp" if exist "header.bmp" echo  [OK] Installer branding artwork found.

:: ── Create icon if missing ────────────────────────────────────────────────────
if not exist "icon.ico" (
    echo  [WARN] icon.ico not found — installer will use default icon.
)

:: ── Require the proprietary LICENSE.txt ──────────────────────────────────────
::   The licence is now a real legal document shipped with the project — do NOT
::   auto-generate a permissive placeholder over it.
if not exist "LICENSE.txt" (
    echo  [ERROR] LICENSE.txt not found. Ship the proprietary licence file with the project.
    pause
    exit /b 1
)

:: ── Create README.txt ────────────────────────────────────────────────────────
(
echo Vanguard Flow NetSentinel v1.0
echo ====================
echo.
echo A real-time network monitoring tool with:
echo   - Live speed test gauges
echo   - DNS monitoring
echo   - Wireshark packet capture frontend
echo   - EtherApe network topology visualiser
echo   - Optional remote client ^(connects to this or another PC^)
echo   - AI-powered capture analysis ^(local, via Ollama — no API key^)
echo   - "System" button opens Task Manager TMOG, the real system
echo     monitor app ^(bundled and installed alongside this app^)
echo   - WSL + Kali Linux installed for pen testing your own network
echo   - "Pen Test" button opens an Nmap scanner with an AI assistant
echo     that can craft scans and recommend next steps
echo.
echo Requirements:
echo   - Windows 10 version 2004 ^(build 19041^) or later, or Windows 11
echo     ^(older Windows 10 still runs the app, just without WSL/Kali^)
echo   - Wireshark ^(silent^) + Npcap ^(one short wizard to click^)
echo   - Nmap ^(silent — installed by the installer^)
echo   - Ollama ^(local AI engine — installed by the build script^)
echo   - Run as Administrator for packet capture
echo.
echo WSL + Kali Linux:
echo   Installed via `wsl --install -d kali-linux` — Kali's own official
echo   WSL install method. A brand-new WSL install commonly needs ONE
echo   restart before Kali is ready; the installer tells you if so.
echo   After that ^(or right away if WSL was already set up^), open a
echo   Command Prompt and run once:
echo     wsl -d kali-linux
echo   to finish Kali's own first-time setup ^(it asks you to create a
echo   UNIX username and password — that's Kali's own step, not this
echo   installer's^). The "Pen Test" button in the app itself now opens
echo   a Kali desktop directly via Win-KeX, once that first-time setup
echo   is done.
echo.
echo Pen Test ^(Nmap scanner^):
echo   The app's "Pen Test" button opens an Nmap scan builder: pick a
echo   target and a scan profile ^(or describe what you want in plain
echo   English and let the built-in AI craft the flags^), watch the scan
echo   run live, then ask the AI to recommend next steps from the
echo   results. A "Kali Desktop ^(Win-KeX^)" button in that same window
echo   still opens the Kali desktop directly, same as before.
echo   Only scan hosts and networks you own or have explicit permission
echo   to test.
echo.
echo AI features:
echo   The app runs its AI locally through Ollama and starts it
echo   automatically on launch. Pull a model once with, e.g.:
echo     ollama pull llama3.2
echo   No Anthropic API key is required.
echo.
echo Usage:
echo   Launch from Desktop or Start Menu shortcut.
echo   Right-click and select "Run as Administrator" for
echo   full packet capture functionality.
echo.
echo Wireshark / Npcap:
echo   Packet capture requires the Npcap driver. The free build of
echo   Npcap cannot be installed silently ^(that is a paid OEM
echo   feature^), so the installer opens its short wizard - just
echo   click through with the defaults. Wireshark itself installs
echo   silently, and Npcap is skipped entirely if already present.
echo   Nmap ^(for the "Pen Test" button^) installs silently right after,
echo   reusing that same Npcap install rather than bringing its own.
echo   If capture fails, try running as Administrator.
) > README.txt

:: ── Step 1: Build PyInstaller exe ────────────────────────────────────────────
echo.
echo  ┌─────────────────────────────────────────┐
echo  │  Step 1: Building SpeedtestMonitor.exe  │
echo  └─────────────────────────────────────────┘
echo.

:: Wipe the old exe FIRST so a failed or blocked rebuild can't masquerade
:: as success -- the same fix Step 1b below already has for the optional
:: client build, now applied here too, for the exe that actually matters.
:: If the exe won't delete, it's locked -- almost always because
:: SpeedtestMonitor.exe is still running (you're testing the live app) or
:: AV is mid-scan. `pyinstaller --noconfirm` does not reliably fail loudly
:: when it can't overwrite a locked target, so trusting its exit code
:: alone isn't enough: it can report success while quietly leaving the
:: previous build's exe sitting in dist\ untouched -- which looks exactly
:: like a real rebuild until you notice the new code just isn't there.
if exist "dist\SpeedtestMonitor.exe" (
    del /f /q "dist\SpeedtestMonitor.exe" >nul 2>&1
    if exist "dist\SpeedtestMonitor.exe" (
        echo  [ERROR] Cannot delete dist\SpeedtestMonitor.exe - it is locked.
        echo          It is almost certainly still running - check Task Manager
        echo          for SpeedtestMonitor.exe and close it ^(or wait for any AV
        echo          scan to finish^), then re-run this script.
        echo          Refusing to build over it and risk shipping a stale exe.
        pause
        exit /b 1
    )
)
if exist "build\SpeedtestMonitor" rmdir /s /q "build\SpeedtestMonitor" >nul 2>&1

python -m PyInstaller speedtest_monitor.spec --noconfirm

if errorlevel 1 (
    echo.
    echo  [ERROR] PyInstaller build failed. Check output above.
    pause & exit /b 1
)

if not exist "dist\SpeedtestMonitor.exe" (
    echo  [ERROR] dist\SpeedtestMonitor.exe not found after build.
    pause & exit /b 1
)
echo.
echo  [OK] SpeedtestMonitor.exe rebuilt fresh from speedtest_monitor.py.

:: -- Step 1b: Build the optional client exe -------------------------------
if exist "nm_client.py" (
    echo.
    echo  +-----------------------------------------+
    echo  ^|  Step 1b: Building NetworkMonitorClient ^|
    echo  +-----------------------------------------+
    echo.

    :: Wipe old artifacts FIRST so a failed rebuild can't masquerade as success.
    :: If the exe won't delete it is locked - the client is still running or AV
    :: is scanning it - which is the usual reason a rebuild "ships the old exe".
    :: Stop loudly rather than embed a stale client.
    if exist "dist\NetworkMonitorClient.exe" (
        del /f /q "dist\NetworkMonitorClient.exe" >nul 2>&1
        if exist "dist\NetworkMonitorClient.exe" (
            echo  [ERROR] Cannot delete dist\NetworkMonitorClient.exe - it is locked.
            echo          It is probably still running or being scanned by AV.
            echo          Close it ^(check Task Manager for NetworkMonitorClient^) and
            echo          re-run this script. Refusing to ship a stale client.
            pause
            exit /b 1
        )
    )
    if exist "build\NetworkMonitorClient" rmdir /s /q "build\NetworkMonitorClient" >nul 2>&1

    :: nm_client.py imports matplotlib lazily, inside a try/except, only when
    :: a tab actually draws a chart, so PyInstaller's static analysis DOES
    :: find and bundle the matplotlib package itself -- but without
    :: --collect-data it never bundles matplotlib's own data directory --
    :: mpl-data: fonts, style sheets, backend registry. That makes
    :: `import matplotlib` succeed at runtime but blow up a moment later
    :: inside matplotlib's own init, which the try/except swallows silently
    :: -- so every chart, Dashboard, Latency, Quality, quietly falls back to
    :: a plain text table with no visible error. speedtest_monitor.spec
    :: already does the equivalent via collect_data_files matplotlib;
    :: --collect-data is the same fix expressed as CLI flags, kept as flags,
    :: not a .spec, so the client stays a single onefile exe, matching what
    :: installer.nsi expects to bundle.
    if exist "icon.ico" (
        python -m PyInstaller --onefile --windowed --name NetworkMonitorClient --icon icon.ico nm_client.py --clean --noconfirm --collect-data matplotlib --hidden-import matplotlib.backends.backend_tkagg --hidden-import numpy
    ) else (
        python -m PyInstaller --onefile --windowed --name NetworkMonitorClient nm_client.py --clean --noconfirm --collect-data matplotlib --hidden-import matplotlib.backends.backend_tkagg --hidden-import numpy
    )

    :: Trust PyInstaller's exit code - NOT the mere presence of an exe, which was
    :: the old bug: a failed build left the previous exe in place and we called
    :: it success.
    if errorlevel 1 (
        echo  [ERROR] PyInstaller failed to build the client - see output above.
        echo          Refusing to continue with a stale/missing client.
        pause
        exit /b 1
    )
    if exist "dist\NetworkMonitorClient.exe" (
        echo  [OK] NetworkMonitorClient.exe rebuilt fresh from nm_client.py.
    ) else (
        echo  [WARN] Build reported success but produced no exe; omitting the client.
    )
) else (
    echo  [INFO] nm_client.py not found - skipping the optional client build.
)

:: -- Step 1c: Build the headless agent exe (for Push Agent's Windows path) --
:: This is a plain onefile build via speedtest_agent.spec (pure stdlib, no
:: heavy deps) rather than nm_client's --onefile CLI invocation above, since
:: a .spec keeps it consistent with speedtest_monitor.spec's own style and
:: makes future tweaks (icon, hidden imports) a one-file edit if ever needed.
:: Push Agent's LINUX path does not need this exe at all: it pushes
:: speedtest_agent.py itself and runs it with the target's own python3,
:: because PyInstaller cannot cross-compile a Linux binary from Windows.
if exist "speedtest_agent.py" (
    echo.
    echo  +-----------------------------------------+
    echo  ^|  Step 1c: Building SpeedtestAgent.exe   ^|
    echo  +-----------------------------------------+
    echo.

    if exist "dist\SpeedtestAgent.exe" (
        del /f /q "dist\SpeedtestAgent.exe" >nul 2>&1
        if exist "dist\SpeedtestAgent.exe" (
            echo  [ERROR] Cannot delete dist\SpeedtestAgent.exe - it is locked.
            echo          Close anything running it and re-run this script.
            pause
            exit /b 1
        )
    )
    if exist "build\speedtest_agent" rmdir /s /q "build\speedtest_agent" >nul 2>&1

    if exist "speedtest_agent.spec" (
        python -m PyInstaller speedtest_agent.spec --noconfirm
    ) else (
        python -m PyInstaller --onefile --console --name SpeedtestAgent speedtest_agent.py --clean --noconfirm
    )

    if errorlevel 1 (
        echo  [ERROR] PyInstaller failed to build the agent - see output above.
        echo          Push Agent's Windows path will have nothing to deploy
        echo          until this is fixed.
        pause
        exit /b 1
    )
    if exist "dist\SpeedtestAgent.exe" (
        echo  [OK] SpeedtestAgent.exe rebuilt fresh from speedtest_agent.py.
    ) else (
        echo  [WARN] Build reported success but produced no exe; Push Agent's
        echo         Windows path will have nothing to deploy.
    )
) else (
    echo  [INFO] speedtest_agent.py not found - skipping the agent build.
    echo         Push Agent will have nothing to deploy to either platform.
)

:: ── Step 2: Build NSIS installer ─────────────────────────────────────────────
echo.
echo  ┌──────────────────────────────────────────────┐
echo  │  Step 2: Building NetworkMonitorSetup.exe    │
echo  └──────────────────────────────────────────────┘
echo.

"!NSIS_PATH!" installer.nsi

if errorlevel 1 (
    echo.
    echo  [ERROR] NSIS build failed. Check output above.
    pause & exit /b 1
)

if not exist "NetworkMonitorSetup.exe" (
    echo  [ERROR] NetworkMonitorSetup.exe not created.
    pause & exit /b 1
)

:: ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║              BUILD COMPLETE — SUCCESS!               ║
echo  ╠══════════════════════════════════════════════════════╣
echo  ║                                                      ║
echo  ║  Output: NetworkMonitorSetup.exe                     ║
echo  ║                                                      ║
echo  ║  This installer will:                                ║
echo  ║    • Install Vanguard Flow NetSentinel to Program Files        ║
echo  ║    • Install Task Manager TMOG (real system monitor) ║
echo  ║    • Install WSL + Kali Linux (pen testing)          ║
echo  ║    • Install Wireshark + Npcap (1 click)             ║
echo  ║    • Install Ollama (local AI engine)                ║
echo  ║    • Install a speed-test CLI (librespeed-cli)       ║
echo  ║    • Optional: remote client app                     ║
echo  ║    • Create Desktop and Start Menu shortcuts         ║
echo  ║    • Register proper uninstaller                     ║
echo  ║                                                      ║
echo  ║  Note: Wireshark, Npcap, Ollama, librespeed-cli and   ║
echo  ║  Kali Linux are NOT bundled into this installer. Each ║
echo  ║  end user's PC downloads them fresh — Kali straight   ║
echo  ║  from Microsoft/Kali via `wsl --install`, the rest    ║
echo  ║  from each project's own site — no third-party NSIS   ║
echo  ║  plugin needed either. Task Manager TMOG IS bundled   ║
echo  ║  directly (no download URL for it exists) — see       ║
echo  ║  TMOGTaskManagerSetup.exe.                            ║
echo  ║                                                      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

for %%A in (NetworkMonitorSetup.exe) do (
    set SIZE=%%~zA
    set /a SIZE_MB=!SIZE! / 1048576
    echo  Installer size: !SIZE_MB! MB
)
echo.

start "" "NetworkMonitorSetup.exe"

pause
