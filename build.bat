@echo off
setlocal EnableDelayedExpansion

title Building SpeedtestMonitor...
echo.
echo ============================================================
echo   SpeedtestMonitor -- PyInstaller build script
echo ============================================================
echo.

:: ── Find a real Python (avoid the Windows Store stub) ───────────────────
set PYTHON=

where py >nul 2>&1
if not errorlevel 1 (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON=py
        goto :found_python
    )
)

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Program Files\Python314\python.exe"
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python312\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%P
        goto :found_python
    )
)

python -m pip --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
    goto :found_python
)

echo [ERROR] Could not find a working Python installation.
echo.
echo   Download Python from https://www.python.org/downloads/
echo   During install, CHECK "Add Python to PATH"
echo   Do NOT use the Microsoft Store version.
echo.
pause
exit /b 1

:found_python
for /f "tokens=*" %%v in ('!PYTHON! --version 2^>^&1') do set PY_VER=%%v
echo [OK] %PY_VER%  at  %PYTHON%
echo.

:: ── Optional file warnings ────────────────────────────────────────────────
if not exist "speedtest.exe" (
    echo [WARNING] speedtest.exe not found - speed tests will not work.
    echo.
)
if not exist "bg.jpg" (
    echo [WARNING] bg.jpg not found - app will use plain dark background.
    echo.
)

:: ── Install dependencies ──────────────────────────────────────────────────
echo [1/3] Installing dependencies...
echo.
%PYTHON% -m pip install --upgrade pip --quiet
if errorlevel 1 ( echo [ERROR] pip upgrade failed. & pause & exit /b 1 )
%PYTHON% -m pip install pyinstaller numpy matplotlib mplcursors pillow --upgrade --quiet
if errorlevel 1 ( echo [ERROR] pip install failed. Check internet connection. & pause & exit /b 1 )
echo       Done.
echo.

:: ── Kill running instance + clean ─────────────────────────────────────────
echo [2/3] Cleaning previous build...
taskkill /f /im SpeedtestMonitor.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul

if exist "dist\SpeedtestMonitor.exe" (
    del /f /q "dist\SpeedtestMonitor.exe" 2>nul
    if exist "dist\SpeedtestMonitor.exe" (
        echo [ERROR] Cannot delete dist\SpeedtestMonitor.exe - still locked.
        echo         Close the app and try again.
        pause
        exit /b 1
    )
)
if exist "build" rmdir /s /q "build" 2>nul
echo       Done.
echo.

:: ── Build ─────────────────────────────────────────────────────────────────
echo [3/3] Building executable (this takes 1-3 minutes)...
echo.
%PYTHON% -m PyInstaller speedtest_monitor.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. See output above for details.
    pause
    exit /b 1
)

:: ── Copy assets into dist ─────────────────────────────────────────────────
if exist "speedtest.exe" ( copy /y "speedtest.exe" "dist\speedtest.exe" >nul & echo [INFO] Copied speedtest.exe )
if exist "bg.jpg"        ( copy /y "bg.jpg"        "dist\bg.jpg"        >nul & echo [INFO] Copied bg.jpg )

:: ── Done ─────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo   BUILD SUCCESSFUL
echo   Executable: dist\SpeedtestMonitor.exe
echo ============================================================
echo.
echo   To distribute: copy everything inside the dist\ folder.
echo.
pause
