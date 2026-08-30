; ============================================================
;  Vanguard Flow NetSentinel — NSIS Installer (Modern UI 2, branded)
;  Requires NSIS 3.x only — no third-party plugins. Downloads go through a
;  small generated PowerShell script + stock ExecWait (see DetailPrint
;  "Downloading ..." sections below) rather than the inetc plugin, which
;  used to require a manual (and, once automated, still unreliable —
;  see CHANGES_this_session.md) install step of its own.
; ============================================================

Unicode True

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "Sections.nsh"
!include "WinVer.nsh"
!include "x64.nsh"

; ── Metadata ────────────────────────────────────────
!define APP_NAME    "Vanguard Flow NetSentinel"
!define APP_EXE     "SpeedtestMonitor.exe"
!define APP_VERSION "1.0.0"
!define PUBLISHER   "Vanguard Flow NetSentinel"
!define REG_KEY     "Software\Microsoft\Windows\CurrentVersion\Uninstall\NetworkMonitor"

; Task Manager TMOG (Dave Plummer / Plummer's Software LLC's free system
; monitor app — the one the video Trevor sent was a recording of). Unlike
; Wireshark/Npcap/Ollama/librespeed-cli above, this is NOT downloaded at
; install time — there's no stable public silent-download URL for it, and
; Trevor supplied the actual installer file directly. So it's bundled into
; this NSIS package (File instruction, SecTMOG below) like the app's own
; exe is, not fetched over the network.
!define TMOG_SETUP    "TMOGTaskManagerSetup.exe"
; It's an Inno Setup installer (confirmed by inspecting its embedded version
; resource: CompanyName "Plummer's Software LLC", ProductName "Task Manager
; TMOG") that we run silently with a forced /DIR= so this app always knows
; exactly where the real exe ends up, without needing to guess its filename.
!define TMOG_SUBDIR   "TaskManagerTMOG"

!define WIRESHARK_URL "https://1.na.dl.wireshark.org/win64/Wireshark-latest-x64.exe"
; Npcap has no "latest" alias URL (unlike Wireshark) -- the version
; below must be bumped by hand periodically. Check https://npcap.com/dist/
; for the current release. Last verified: npcap 1.88 (2026-08-26).
!define NPCAP_URL     "https://npcap.com/dist/npcap-1.88.exe"
!define OLLAMA_URL    "https://ollama.com/download/OllamaSetup.exe"

; Nmap's Windows self-installer has no "latest" alias URL either (like
; Npcap) -- the version below must be bumped by hand periodically. Check
; https://nmap.org/download.html for the current release ("Latest stable
; release self-installer"). Last verified: nmap 7.991 (2026-08-29).
!define NMAP_URL      "https://nmap.org/dist/nmap-7.991-setup.exe"

; librespeed-cli (LGPL, github.com/librespeed/speedtest-cli) — an open-source
; drop-in for Ookla's speed-test CLI, which we deliberately do NOT bundle or
; download (its licence forbids redistribution). Pinned to a specific release
; like Npcap, since GitHub release assets don't have a "latest" filename
; either. Check https://github.com/librespeed/speedtest-cli/releases for the
; current version when bumping this.
!define LIBRESPEED_URL "https://github.com/librespeed/speedtest-cli/releases/download/v1.0.14/librespeed-cli_1.0.14_windows_amd64.zip"

; ── Installer settings ────────────────────────────────
Name            "${APP_NAME} ${APP_VERSION}"
OutFile         "NetworkMonitorSetup.exe"
InstallDir      "$PROGRAMFILES64\NetworkMonitor"
InstallDirRegKey HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
ShowInstDetails show
ShowUnInstDetails show
BrandingText    "${APP_NAME} ${APP_VERSION}"
SetCompressor   /SOLID lzma

; ── Install presets ──────────────────────────────────
;   1 = Full (monitor + capture + AI) · 2 = Client only.
;   These let a second machine install just the viewer without the monitor,
;   Wireshark/Npcap or Ollama.
InstType "Full  (monitor + capture + AI)"
InstType "Client only"

; ── Modern UI look ───────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_COMPONENTSPAGE_SMALLDESC

; Branding art is optional — the build still works without it.
!if /FileExists "icon.ico"
  !define MUI_ICON   "icon.ico"
  !define MUI_UNICON "icon.ico"
!endif
!if /FileExists "header.bmp"
  !define MUI_HEADERIMAGE_BITMAP        "header.bmp"
  !define MUI_HEADERIMAGE_UNBITMAP      "header.bmp"
!endif
!if /FileExists "welcome.bmp"
  !define MUI_WELCOMEFINISHPAGE_BITMAP   "welcome.bmp"
  !define MUI_UNWELCOMEFINISHPAGE_BITMAP "welcome.bmp"
!endif

!define MUI_WELCOMEPAGE_TITLE "${APP_NAME} ${APP_VERSION}"
!define MUI_WELCOMEPAGE_TEXT  "Live network topology, packet capture, alerting, VDI session health and local AI analysis — in one app.$\r$\n$\r$\nSetup will install ${APP_NAME} and the capture components it needs.$\r$\n$\r$\nClose other applications before continuing, then click Next."

!define MUI_LICENSEPAGE_TEXT_TOP    "Please review the licence terms."
!define MUI_LICENSEPAGE_BUTTON      "I Agree"

!define MUI_DIRECTORYPAGE_TEXT_TOP  "${APP_NAME} will be installed in the folder below. To choose a different location, click Browse."

!define MUI_FINISHPAGE_TITLE     "${APP_NAME} is installed"
!define MUI_FINISHPAGE_TEXT      "${APP_NAME} has been installed on your computer.$\r$\n$\r$\nRun it as Administrator for packet capture and firewall features."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION "LaunchApp"
!define MUI_FINISHPAGE_RUN_TEXT  "Launch ${APP_NAME} now"
!define MUI_FINISHPAGE_LINK      "Open the dashboard at http://localhost:8765"
!define MUI_FINISHPAGE_LINK_LOCATION "http://localhost:8765"

; ── Pages ───────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE ComponentsLeave
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Installer init ─────────────────────────────────────────
Function .onInit
    ${IfNot} ${AtLeastWin10}
        MessageBox MB_ICONSTOP|MB_OK "Vanguard Flow NetSentinel requires Windows 10 or later."
        Abort
    ${EndIf}
    ${IfNot} ${RunningX64}
        MessageBox MB_ICONSTOP|MB_OK "Vanguard Flow NetSentinel requires 64-bit Windows."
        Abort
    ${EndIf}
FunctionEnd

; ── Main section ───────────────────────────────────────────
Section "Vanguard Flow NetSentinel (monitor app)" SecMain
    SectionIn 1
    SetOutPath "$INSTDIR"
    File "dist\${APP_EXE}"
    File /nonfatal "bg.jpg"
    ; Ookla's speedtest CLI is deliberately NOT redistributed: its licence
    ; restricts commercial redistribution. The app finds whichever CLI is
    ; installed (librespeed-cli, speedtest-cli or Ookla) at runtime.
    File /nonfatal "LICENSE.txt"
    File /nonfatal "README.txt"
SectionEnd

; ── Task Manager TMOG (the real system-monitor app, bundled + auto-installed) ──
; The app's own "System" button launches this real, standalone app instead of
; a built-in reimplementation. Installed silently into a FIXED subfolder of
; our own install dir ($INSTDIR\${TMOG_SUBDIR}) so speedtest_monitor.py can
; find its exe deterministically — it doesn't have to guess or search the
; whole filesystem, just list that one folder for the first *.exe that isn't
; the Inno Setup uninstaller.
!if /FileExists "${TMOG_SETUP}"
Section "Task Manager TMOG (real system monitor)" SecTMOG
    SectionIn 1
    ; Skip if a previous run of this installer already put it there.
    IfFileExists "$INSTDIR\${TMOG_SUBDIR}\unins000.exe" tmog_skip 0

    SetOutPath "$TEMP"
    File "${TMOG_SETUP}"
    DetailPrint "Installing Task Manager TMOG..."
    ; Inno Setup standard silent-install command line (documented at
    ; jrsoftware.org/ishelp, "Setup Command Line Parameters"):
    ;   /VERYSILENT           no UI at all
    ;   /SUPPRESSMSGBOXES     don't stop for its own info/error dialogs
    ;   /NORESTART            never reboot on our behalf
    ;   /SP-                  skip the "This will install... continue?" prompt
    ;   /DIR=                 force the install directory (this is what lets
    ;                         us find the exe afterwards without guessing)
    ExecWait '"$TEMP\${TMOG_SETUP}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="$INSTDIR\${TMOG_SUBDIR}"' $0
    Delete "$TEMP\${TMOG_SETUP}"
    IfFileExists "$INSTDIR\${TMOG_SUBDIR}\*.exe" tmog_ok 0
    DetailPrint "Task Manager TMOG install did not produce an exe (exit code $0) — the System button will show its own error if it can't find one."
    Goto tmog_done

    tmog_ok:
    DetailPrint "Task Manager TMOG installed."
    Goto tmog_done

    tmog_skip:
    DetailPrint "Task Manager TMOG already installed here — skipping."

    tmog_done:
SectionEnd
!endif

; ── Npcap + Wireshark ───────────────────────────────
; NOTE: the free build of Npcap does NOT support silent (/S) installation —
; that is a paid Npcap OEM feature. Attempting it just fails. So we install
; Npcap interactively (one short wizard) BEFORE Wireshark; Wireshark then sees
; Npcap already present and its own /S install completes without prompting.
Section "Wireshark + Npcap (for capture)" SecWireshark
    SectionIn 1

    ; ---- Npcap (capture driver) ----
    ReadRegStr $1 HKLM "SOFTWARE\WOW6432Node\Npcap" "InstallDir"
    StrCmp $1 "" 0 npcap_present
    ReadRegStr $1 HKLM "SOFTWARE\Npcap" "InstallDir"
    StrCmp $1 "" 0 npcap_present
    ; $WINDIR\Sysnative, not $WINDIR\System32: this installer is a 32-bit
    ; process (NSIS default target) running on the 64-bit Windows this app
    ; requires, so plain "System32" gets silently redirected by WOW64 to
    ; SysWOW64 instead — the real (64-bit) System32 is only reachable
    ; through the Sysnative alias from a 32-bit process. Using System32
    ; here would make a real Npcap install invisible to this check.
    IfFileExists "$WINDIR\Sysnative\Npcap\wpcap.dll" npcap_present 0
    IfFileExists "$WINDIR\Sysnative\wpcap.dll"        npcap_present 0

    DetailPrint "Downloading Npcap (packet capture driver)..."
    SetOutPath "$TEMP"
    Delete "$TEMP\npcap_setup.exe"
    FileOpen $2 "$TEMP\dl_npcap.ps1" w
    FileWrite $2 '$$ProgressPreference = "SilentlyContinue"$\r$\n'
    FileWrite $2 'try { Invoke-WebRequest -Uri "${NPCAP_URL}" -OutFile "$TEMP\npcap_setup.exe" -UseBasicParsing } catch {}$\r$\n'
    FileClose $2
    ExecWait 'powershell -NoProfile -ExecutionPolicy Bypass -File "$TEMP\dl_npcap.ps1"' $0
    Delete "$TEMP\dl_npcap.ps1"
    IfFileExists "$TEMP\npcap_setup.exe" npcap_install 0
    MessageBox MB_OK "Could not download Npcap.$\r$\nInstall it manually from https://npcap.com/ — packet capture will not work without it."
    Goto npcap_done

    npcap_install:
    MessageBox MB_OK|MB_ICONINFORMATION "Npcap installer will now open.$\r$\n$\r$\nThe free version of Npcap cannot be installed silently, so please click through its short wizard (the defaults are fine).$\r$\n$\r$\nSetup will continue automatically afterwards."
    DetailPrint "Running Npcap installer (user interaction required)..."
    ExecWait '"$TEMP\npcap_setup.exe"' $0
    Delete "$TEMP\npcap_setup.exe"
    DetailPrint "Npcap installer finished (exit code $0)."
    Goto npcap_done

    npcap_present:
    DetailPrint "Npcap already installed — skipping."

    npcap_done:

    ; ---- Wireshark / tshark ----
    IfFileExists "$PROGRAMFILES64\Wireshark\tshark.exe" ws_skip 0
    IfFileExists "$PROGRAMFILES\Wireshark\tshark.exe"   ws_skip 0

    DetailPrint "Downloading Wireshark..."
    SetOutPath "$TEMP"
    Delete "$TEMP\wireshark_setup.exe"
    FileOpen $2 "$TEMP\dl_wireshark.ps1" w
    FileWrite $2 '$$ProgressPreference = "SilentlyContinue"$\r$\n'
    FileWrite $2 'try { Invoke-WebRequest -Uri "${WIRESHARK_URL}" -OutFile "$TEMP\wireshark_setup.exe" -UseBasicParsing } catch {}$\r$\n'
    FileClose $2
    ExecWait 'powershell -NoProfile -ExecutionPolicy Bypass -File "$TEMP\dl_wireshark.ps1"' $0
    Delete "$TEMP\dl_wireshark.ps1"
    IfFileExists "$TEMP\wireshark_setup.exe" ws_install 0
    MessageBox MB_OK "Could not download Wireshark.$\r$\nInstall manually from https://www.wireshark.org/"
    Goto ws_done

    ws_install:
    DetailPrint "Installing Wireshark silently..."
    ExecWait '"$TEMP\wireshark_setup.exe" /S /desktopicon=no' $0
    Delete "$TEMP\wireshark_setup.exe"
    Goto ws_done

    ws_skip:
    DetailPrint "Wireshark already installed."

    ws_done:
SectionEnd

; ── Nmap (network scanner) ───────────────────────────────
; Powers the app's own "Pen Test" button (the Nmap scanner GUI). Placed
; after the Wireshark+Npcap section on purpose: Nmap's Windows installer
; bundles its own Npcap and will offer to install it, but Npcap is already
; present by this point (installed above, or already on the machine), so
; Nmap's installer just detects that and skips its own copy — no double
; install, no interactive Npcap wizard a second time.
Section "Nmap (network scanner)" SecNmap
    SectionIn 1

    ; Skip if already installed. Nmap's installer defaults to
    ; $PROGRAMFILES\Nmap regardless of this being a 64-bit machine (it
    ; ships a single 32-bit-compatible build), but check both Program
    ; Files locations the way the Wireshark check above does, in case a
    ; previous install landed in the native 64-bit one instead.
    IfFileExists "$PROGRAMFILES\Nmap\nmap.exe"   nmap_skip 0
    IfFileExists "$PROGRAMFILES64\Nmap\nmap.exe" nmap_skip 0

    DetailPrint "Downloading Nmap..."
    SetOutPath "$TEMP"
    Delete "$TEMP\nmap_setup.exe"
    FileOpen $2 "$TEMP\dl_nmap.ps1" w
    FileWrite $2 '$$ProgressPreference = "SilentlyContinue"$\r$\n'
    FileWrite $2 'try { Invoke-WebRequest -Uri "${NMAP_URL}" -OutFile "$TEMP\nmap_setup.exe" -UseBasicParsing } catch {}$\r$\n'
    FileClose $2
    ExecWait 'powershell -NoProfile -ExecutionPolicy Bypass -File "$TEMP\dl_nmap.ps1"' $0
    Delete "$TEMP\dl_nmap.ps1"
    IfFileExists "$TEMP\nmap_setup.exe" nmap_install 0
    MessageBox MB_OK "Could not download Nmap.$\r$\nThe Pen Test button needs it — install manually from https://nmap.org/ or click Re-check inside that window afterwards."
    Goto nmap_done

    nmap_install:
    DetailPrint "Installing Nmap silently..."
    ; Nmap's installer is itself NSIS-based and supports the standard /S
    ; silent switch (documented at nmap.org/book/inst-windows.html). With
    ; Npcap already present (see comment above the Section line) this
    ; completes with no prompts.
    ExecWait '"$TEMP\nmap_setup.exe" /S' $0
    Delete "$TEMP\nmap_setup.exe"
    IfFileExists "$PROGRAMFILES\Nmap\nmap.exe"   nmap_ok 0
    IfFileExists "$PROGRAMFILES64\Nmap\nmap.exe" nmap_ok 0
    DetailPrint "Nmap install did not produce an exe (exit code $0) — the Pen Test button will show its own 'not found' message with a Re-check option."
    Goto nmap_done

    nmap_ok:
    DetailPrint "Nmap installed."
    Goto nmap_done

    nmap_skip:
    DetailPrint "Nmap already installed — skipping."

    nmap_done:
SectionEnd

; ── Ollama (local AI engine) ───────────────────────────────
;    Powers the app's AI features locally (no API key). The app starts
;    Ollama automatically on launch; this just makes sure it's installed.
Section "Ollama (local AI engine)" SecOllama
    SectionIn 1
    ; Skip if already present — check the per-user default and a system-wide path.
    IfFileExists "$LOCALAPPDATA\Programs\Ollama\ollama.exe" ollama_skip 0
    IfFileExists "$PROGRAMFILES64\Ollama\ollama.exe"        ollama_skip 0

    DetailPrint "Downloading Ollama..."
    SetOutPath "$TEMP"
    Delete "$TEMP\OllamaSetup.exe"
    FileOpen $2 "$TEMP\dl_ollama.ps1" w
    FileWrite $2 '$$ProgressPreference = "SilentlyContinue"$\r$\n'
    FileWrite $2 'try { Invoke-WebRequest -Uri "${OLLAMA_URL}" -OutFile "$TEMP\OllamaSetup.exe" -UseBasicParsing } catch {}$\r$\n'
    FileClose $2
    ExecWait 'powershell -NoProfile -ExecutionPolicy Bypass -File "$TEMP\dl_ollama.ps1"' $0
    Delete "$TEMP\dl_ollama.ps1"
    IfFileExists "$TEMP\OllamaSetup.exe" ollama_install 0
    MessageBox MB_OK "Could not download Ollama.$\r$\nThe app's AI needs Ollama - install manually from https://ollama.com/"
    Goto ollama_done

    ollama_install:
    DetailPrint "Installing Ollama silently..."
    ExecWait '"$TEMP\OllamaSetup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART' $0
    Delete "$TEMP\OllamaSetup.exe"
    DetailPrint "Ollama installed. First AI use will pull a model, or run: ollama pull llama3.2"
    Goto ollama_done

    ollama_skip:
    DetailPrint "Ollama already installed."

    ollama_done:
SectionEnd

; ── Speed-test CLI ───────────────────────────────────────────
; Ookla's own CLI is proprietary and its licence forbids redistribution, so
; we never bundle or download it. librespeed-cli is LGPL and fine to fetch
; fresh the same way as Wireshark/Npcap/Ollama above. Skipped if the user
; already has ANY supported engine (librespeed-cli, speedtest-cli or Ookla's)
; on PATH — this only fills the gap when nothing is available.
Section "Speed-test CLI (librespeed-cli)" SecSpeedtest
    SectionIn 1

    IfFileExists "$INSTDIR\librespeed-cli.exe" st_skip 0

    ; ExecToStack pushes exit code then output (output on top) — pop BOTH
    ; every time, or the leftover output string corrupts the next Pop.
    nsExec::ExecToStack 'where librespeed-cli'
    Pop $0
    Pop $1
    StrCmp $0 "0" st_skip 0
    nsExec::ExecToStack 'where speedtest-cli'
    Pop $0
    Pop $1
    StrCmp $0 "0" st_skip 0
    nsExec::ExecToStack 'where speedtest'
    Pop $0
    Pop $1
    StrCmp $0 "0" st_skip 0

    DetailPrint "Downloading librespeed-cli (open-source speed-test engine)..."
    SetOutPath "$TEMP"
    Delete "$TEMP\librespeed-cli.zip"
    RMDir /r "$TEMP\librespeed_extract"
    ; One script does download + extract + copy. $INSTDIR/$TEMP can contain
    ; spaces (e.g. "Program Files"), which is fragile to nest inside an
    ; already-quoted inline command, and the exe is found by searching the
    ; extracted tree recursively rather than assuming the zip's internal
    ; layout. Silent try/catch — NSIS checks the result via IfFileExists
    ; below rather than trying to parse PowerShell's own error output.
    FileOpen $2 "$TEMP\install_librespeed.ps1" w
    FileWrite $2 '$$ProgressPreference = "SilentlyContinue"$\r$\n'
    FileWrite $2 '$$ErrorActionPreference = "Stop"$\r$\n'
    FileWrite $2 'try {$\r$\n'
    FileWrite $2 '  Invoke-WebRequest -Uri "${LIBRESPEED_URL}" -OutFile "$TEMP\librespeed-cli.zip" -UseBasicParsing$\r$\n'
    FileWrite $2 '  Expand-Archive -Path "$TEMP\librespeed-cli.zip" -DestinationPath "$TEMP\librespeed_extract" -Force$\r$\n'
    FileWrite $2 '  $$found = Get-ChildItem -Path "$TEMP\librespeed_extract" -Recurse -Filter "librespeed-cli.exe" | Select-Object -First 1$\r$\n'
    FileWrite $2 '  if ($$found) { Copy-Item $$found.FullName -Destination "$INSTDIR\librespeed-cli.exe" -Force }$\r$\n'
    FileWrite $2 '} catch {}$\r$\n'
    FileClose $2

    ExecWait 'powershell -NoProfile -ExecutionPolicy Bypass -File "$TEMP\install_librespeed.ps1"' $0
    Delete "$TEMP\librespeed-cli.zip"
    Delete "$TEMP\install_librespeed.ps1"
    RMDir /r "$TEMP\librespeed_extract"

    IfFileExists "$INSTDIR\librespeed-cli.exe" st_ok 0
    MessageBox MB_OK "Could not set up the speed-test CLI.$\r$\nSpeed tests will not work until you install one — see Settings, or download librespeed-cli from https://github.com/librespeed/speedtest-cli/releases"
    Goto st_done

    st_ok:
    DetailPrint "librespeed-cli installed."
    Goto st_done

    st_skip:
    DetailPrint "A speed-test CLI is already available — skipping."

    st_done:
SectionEnd

; ── WSL + Kali Linux (pen testing environment) ──────────────────────────────
; Installs/enables Windows Subsystem for Linux, then installs Kali Linux as
; a WSL distro. This is step one of a two-step plan Trevor asked for: get a
; real, working Kali install first; a GUI to drive specific tools inside it
; is a separate follow-up, not part of this section.
;
; `wsl --install -d kali-linux` is Kali's own officially documented WSL
; install method (kali.org/docs/wsl/wsl-preparations), not a third-party
; trick, and needs no download URL of our own — WSL fetches the Kali image
; itself from Microsoft's own distribution. No File/bundling needed here,
; unlike Wireshark/Ollama/librespeed above.
;
; IMPORTANT: this could not be run or observed on a real Windows machine
; from this build environment (no Windows box here) — the commands below
; are Microsoft's and Kali's own documented commands, not guesses, but if
; anything behaves differently than described here, say what actually
; happened on your machine and it gets fixed against that, not against
; what the docs say it should do.
Section "WSL + Kali Linux (pen testing)" SecWSLKali
    SectionIn 1

    ; wsl.exe ships inside Windows itself; if it's missing, this build of
    ; Windows predates WSL --install entirely (needs Windows 10 2004+ /
    ; Windows 11) and there's nothing this section can do.
    ;
    ; BUG FOUND ON A REAL RUN: this used to check $WINDIR\System32\wsl.exe
    ; and reported "not found" on a machine that genuinely had WSL working.
    ; Cause: this installer is a 32-bit process (NSIS's default target)
    ; running on the 64-bit Windows this app requires, so a plain
    ; "System32" path gets silently redirected by WOW64 File System
    ; Redirection to SysWOW64 instead — and wsl.exe, being 64-bit-only,
    ; was never there to find. $WINDIR\Sysnative is the documented
    ; Microsoft alias that lets a 32-bit process reach the REAL (64-bit)
    ; System32 instead of the redirected view. Same class of bug just
    ; fixed on the Npcap check above, for the same reason.
    IfFileExists "$WINDIR\Sysnative\wsl.exe" wsl_present 0
    DetailPrint "wsl.exe not found — Windows Subsystem for Linux isn't available on this PC. Skipping Kali Linux."
    MessageBox MB_OK|MB_ICONINFORMATION "Windows Subsystem for Linux isn't available on this PC (wsl.exe not found), so Kali Linux was not installed.$\r$\nWSL needs Windows 10 version 2004 (build 19041) or later, or Windows 11."
    Goto wsl_kali_done

    wsl_present:
    ; Already installed? `wsl -l -q` lists installed distro names only, one
    ; per line, meant for scripts like this (no "(Default)" markers to
    ; strip). findstr's EXIT CODE (0 = matched, 1 = no match) is the actual
    ; signal checked here via $0, not the captured text in $1.
    ; NOTE: `wsl.exe` output is known to sometimes come out as UTF-16 when
    ; piped, which can make findstr miss a real match on some systems — if
    ; that happens here, this just falls through to attempting the install
    ; again, and `wsl --install` is itself safe to re-run against a distro
    ; that's already present (it just reports so and does nothing further),
    ; so the worst case is a harmless extra check, not a broken state.
    nsExec::ExecToStack 'cmd /c "$WINDIR\Sysnative\wsl.exe" -l -q | findstr /i /x "kali-linux"'
    Pop $0
    Pop $1
    StrCmp $0 "0" kali_present 0

    DetailPrint "Installing WSL + Kali Linux — this downloads a real Linux distro image and can take several minutes..."
    ; --no-launch: don't pop open an interactive console at the end. This is
    ; a silent installer; Kali's own first-run "create a UNIX username and
    ; password" wizard needs a person answering it, so that step is left
    ; for the user to run once themselves afterwards (message below),
    ; rather than this installer trying to fake keystrokes into it.
    ExecWait '"$WINDIR\Sysnative\wsl.exe" --install -d kali-linux --no-launch' $0
    DetailPrint "wsl --install exit code: $0"

    ; A brand-new WSL install (Windows features not previously enabled) very
    ; commonly needs one restart before `wsl` fully works — that's a
    ; Windows/WSL constraint, not something this installer can skip past.
    ; Re-check rather than assume either outcome.
    nsExec::ExecToStack 'cmd /c "$WINDIR\Sysnative\wsl.exe" -l -q | findstr /i /x "kali-linux"'
    Pop $0
    Pop $1
    StrCmp $0 "0" kali_ready 0
    MessageBox MB_OK|MB_ICONINFORMATION "WSL and Kali Linux were installed, but Windows needs a RESTART before Kali is ready.$\r$\n$\r$\nAfter restarting, open Command Prompt and run:$\r$\n    wsl -d kali-linux$\r$\nonce, to finish Kali's own first-time setup (it will ask you to create a UNIX username and password — that's Kali's own setup step, not this installer)."
    Goto wsl_kali_done

    kali_ready:
    MessageBox MB_OK|MB_ICONINFORMATION "Kali Linux (WSL) is installed.$\r$\n$\r$\nOpen Command Prompt and run:$\r$\n    wsl -d kali-linux$\r$\nonce, to finish Kali's own first-time setup (it will ask you to create a UNIX username and password)."
    Goto wsl_kali_done

    kali_present:
    DetailPrint "Kali Linux (WSL) already installed — skipping."

    wsl_kali_done:
SectionEnd

; ── Shortcuts ──────────────────────────────────────────────
; ── Optional remote client ───────────────────────────────────
; Unselected by default: most people run the full app. Install this on a
; SECOND machine to watch the monitor running on this one.
Section /o "Remote client app" SecClient
    SectionIn 2
    SetOutPath "$INSTDIR"
    ; NOTE: the old code guarded this with a RUNTIME `IfFileExists "dist\..."`,
    ; evaluated on the END USER's machine — where no `dist\` folder exists — so
    ; it ALWAYS jumped to client_missing and the File below was NEVER extracted,
    ; even when the component was ticked. The correct guard is COMPILE-TIME
    ; (`!if /FileExists`), evaluated on the build machine: it either embeds and
    ; installs the client, or omits it cleanly when it wasn't built.
!if /FileExists "dist\NetworkMonitorClient.exe"
    File "dist\NetworkMonitorClient.exe"
    ; Own shortcuts — in a client-only install the main shortcuts section does
    ; not run, so create the Start Menu folder here rather than relying on it.
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME} Client.lnk" \
        "$INSTDIR\NetworkMonitorClient.exe"
    CreateShortcut "$DESKTOP\${APP_NAME} Client.lnk" \
        "$INSTDIR\NetworkMonitorClient.exe"
    DetailPrint "Remote client installed."
!else
    DetailPrint "Client executable not found in the build — skipped."
!endif
SectionEnd

Section "Desktop & Start Menu shortcuts" SecShortcuts
    SectionIn 1
    CreateShortcut "$DESKTOP\Vanguard Flow NetSentinel.lnk" "$INSTDIR\${APP_EXE}"
    CreateDirectory "$SMPROGRAMS\Vanguard Flow NetSentinel"
    CreateShortcut "$SMPROGRAMS\Vanguard Flow NetSentinel\Vanguard Flow NetSentinel.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$SMPROGRAMS\Vanguard Flow NetSentinel\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Registration (hidden, ALWAYS runs) ─────────────────────
; Writes the uninstaller + Add/Remove Programs entry regardless of which
; components were chosen, so a client-only install is registered and
; uninstallable too. (This used to live in SecMain, which no longer runs
; when the monitor is deselected.)
Section "-post" SecPost
    SetOutPath "$INSTDIR"
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    WriteRegStr   HKLM "${REG_KEY}" "DisplayName"          "${APP_NAME}"
    WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"       "${APP_VERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "Publisher"            "${PUBLISHER}"
    WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"      "$INSTDIR"
    WriteRegStr   HKLM "${REG_KEY}" "UninstallString"      '"$INSTDIR\Uninstall.exe"'
    WriteRegStr   HKLM "${REG_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKLM "${REG_KEY}" "NoModify"             1
    WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"             1
    WriteRegDWORD HKLM "${REG_KEY}" "EstimatedSize"        81920

    ; DisplayIcon: prefer the monitor exe, fall back to the client (client-only).
    IfFileExists "$INSTDIR\${APP_EXE}" post_icon_main post_icon_client
    post_icon_main:
        WriteRegStr HKLM "${REG_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE},0"
        Goto post_icon_done
    post_icon_client:
        WriteRegStr HKLM "${REG_KEY}" "DisplayIcon" "$INSTDIR\NetworkMonitorClient.exe,0"
    post_icon_done:
SectionEnd

; Defined AFTER the sections so ${SecMain}/${SecClient} resolve.
; Don't let the user proceed with nothing selected now that the monitor is
; deselectable — require the monitor app OR the client.
Function ComponentsLeave
    SectionGetFlags ${SecMain} $0
    IntOp $0 $0 & ${SF_SELECTED}
    SectionGetFlags ${SecClient} $1
    IntOp $1 $1 & ${SF_SELECTED}
    IntOp $2 $0 + $1
    ${If} $2 = 0
        MessageBox MB_ICONEXCLAMATION|MB_OK "Select at least the monitor app or the remote client."
        Abort
    ${EndIf}
FunctionEnd

; Launch whichever app was actually installed (monitor for full, client for a
; client-only install) from the Finish page.
Function LaunchApp
    IfFileExists "$INSTDIR\${APP_EXE}" launch_main launch_client
    launch_main:
        Exec '"$INSTDIR\${APP_EXE}"'
        Goto launch_done
    launch_client:
        Exec '"$INSTDIR\NetworkMonitorClient.exe"'
    launch_done:
FunctionEnd

; ── Component descriptions ─────────────────────────────
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}      "The ${APP_NAME} monitor app — captures, tests and serves the dashboard. Choose the 'Client only' preset to skip this and install just the viewer."
!if /FileExists "${TMOG_SETUP}"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecTMOG}      "Task Manager TMOG — the real system-monitor app (Dave Plummer / Plummer's Software LLC). The app's own 'System' button opens this instead of a built-in copy."
!endif
  !insertmacro MUI_DESCRIPTION_TEXT ${SecWireshark} "Wireshark and the Npcap driver — needed for packet capture, live topology and flow analysis. Npcap shows a short wizard (its free build cannot install silently)."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecNmap}      "Nmap — the network scanner behind the app's 'Pen Test' button. Installs silently; needs Npcap (above) for full functionality."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecOllama}    "Ollama runs the AI features locally on this machine. No API key and no cloud account needed."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecSpeedtest} "librespeed-cli, an open-source speed-test engine — needed for the speed gauges. Skipped if you already have a compatible CLI on PATH."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecWSLKali}   "Windows Subsystem for Linux + Kali Linux — a real pen-testing environment for your own network. Needs Windows 10 2004+ or Windows 11; may need one restart on a first-ever WSL install."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecClient}    "A standalone client that connects to a Vanguard Flow NetSentinel running on this or another PC and shows its dashboard, alerts, devices, quality, heatmap and outages. Install this on a second machine."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecShortcuts} "Desktop and Start Menu shortcuts."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ── Uninstaller ────────────────────────────────────────────
Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\NetworkMonitorClient.exe"
    Delete "$INSTDIR\bg.jpg"
    Delete "$INSTDIR\speedtest.exe"
    Delete "$INSTDIR\librespeed-cli.exe"
    Delete "$INSTDIR\LICENSE.txt"
    Delete "$INSTDIR\README.txt"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir  "$INSTDIR"
    Delete "$DESKTOP\Vanguard Flow NetSentinel.lnk"
    Delete "$DESKTOP\${APP_NAME} Client.lnk"
    Delete "$SMPROGRAMS\Vanguard Flow NetSentinel\Vanguard Flow NetSentinel.lnk"
    Delete "$SMPROGRAMS\Vanguard Flow NetSentinel\${APP_NAME} Client.lnk"
    Delete "$SMPROGRAMS\Vanguard Flow NetSentinel\Uninstall.lnk"
    RMDir  "$SMPROGRAMS\Vanguard Flow NetSentinel"
    DeleteRegKey HKLM "${REG_KEY}"
    MessageBox MB_OK "Vanguard Flow NetSentinel has been uninstalled.$\r$\nWireshark, Npcap, Nmap, Ollama, Task Manager TMOG and WSL/Kali Linux were NOT removed — uninstall those separately (Apps & Features for the first five; 'wsl --unregister kali-linux' for Kali) if you want them gone too."
SectionEnd
