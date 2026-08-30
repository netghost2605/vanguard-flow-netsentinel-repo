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

:: ── Check / install PyInstaller ───────────────────────────────────────────────
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo  Installing PyInstaller...
    pip install pyinstaller --quiet
)
echo  [OK] PyInstaller ready.

:: ── Check / install Python dependencies ──────────────────────────────────────
echo  Installing Python dependencies...
pip install numpy matplotlib mplcursors Pillow --quiet
:: nvidia-ml-py (imported as "pynvml") gives the System Monitor real NVIDIA
:: GPU readings — name, utilization, memory, power, temperature, clock — via
:: NVML. It is pure Python (no compiled extension), so bundling it here means
:: PyInstaller's own import scan of speedtest_monitor.py picks it up and
:: freezes it into SpeedtestMonitor.exe automatically; nothing else to wire
:: up. It's a no-op on a machine with no NVIDIA GPU/driver — the app already
:: catches that ImportError/NVMLError itself and shows "Unavailable" with the
:: real reason, never a fabricated reading. Installed here (build time) so it
:: ships INSIDE the exe; end users never need to pip install anything.
pip install nvidia-ml-py --quiet
echo  [OK] Python dependencies installed (including nvidia-ml-py for GPU readings).

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

:: ── Optional: pull the default AI model so the app works out of the box ───────
if defined OLLAMA_EXE (
    echo.
    echo  The app's AI uses an Ollama model ^(default: llama3.2^).
    echo  If you have already pulled a model ^(e.g. qwen3:8b^) you can skip this.
    choice /c YN /n /m "  Pull llama3.2 now (~2 GB)? [Y/N]: "
    if !errorlevel! equ 1 (
        echo  [..] Pulling llama3.2 — this can take a few minutes...
        "!OLLAMA_EXE!" pull llama3.2
        echo  [OK] Model ready.
    ) else (
        echo  [i]  Skipped. You can pull one anytime with:  ollama pull llama3.2
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

pyinstaller speedtest_monitor.spec --noconfirm

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
echo  [OK] SpeedtestMonitor.exe built successfully.

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

    if exist "icon.ico" (
        pyinstaller --onefile --windowed --name NetworkMonitorClient --icon icon.ico nm_client.py --clean --noconfirm
    ) else (
        pyinstaller --onefile --windowed --name NetworkMonitorClient nm_client.py --clean --noconfirm
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
