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
:: A speed-test CLI is NOT bundled. Ookla's licence restricts redistribution,
:: so the app locates one at runtime: librespeed-cli (LGPL), speedtest-cli
:: (Apache) or Ookla's own if the user already has it.
if not exist "speedtest.exe" (
    echo  [INFO] No speedtest.exe here - fine, it is not bundled.
    echo         Users install a CLI themselves; the app finds it automatically.
)

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
echo  [OK] Python dependencies installed.

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
    echo  Also install the inetc plugin: https://nsis.sourceforge.io/Inetc_plug-in
    echo.
    echo  After installing NSIS, re-run this script.
    pause & exit /b 1
)
echo  [OK] NSIS found.

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
echo.
echo Requirements:
echo   - Windows 10 or later ^(64-bit^)
echo   - Wireshark ^(silent^) + Npcap ^(one short wizard to click^)
echo   - Ollama ^(local AI engine — installed by the build script^)
echo   - Run as Administrator for packet capture
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
echo   Nmap is NOT required and is no longer installed.
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
    echo  Make sure the inetc plugin is installed:
    echo  https://nsis.sourceforge.io/Inetc_plug-in
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
echo  ║    • Install Wireshark + Npcap (1 click)             ║
echo  ║    • Install Ollama (local AI engine)                ║
echo  ║    • Optional: remote client app                     ║
echo  ║    • Create Desktop and Start Menu shortcuts         ║
echo  ║    • Register proper uninstaller                     ║
echo  ║                                                      ║
echo  ║  Note: Wireshark, Npcap and Ollama are NOT bundled   ║
echo  ║  into this installer. Each end user's PC downloads   ║
echo  ║  them fresh from the official Wireshark/Npcap/Ollama ║
echo  ║  sites the first time the installer runs.            ║
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
