; ============================================================
;  Vanguard Flow NetSentinel — NSIS Installer (Modern UI 2, branded)
;  Requires NSIS 3.x + inetc plugin
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

!define WIRESHARK_URL "https://1.na.dl.wireshark.org/win64/Wireshark-latest-x64.exe"
; Npcap has no "latest" alias URL (unlike Wireshark) -- the version
; below must be bumped by hand periodically. Check https://npcap.com/dist/
; for the current release. Last verified: npcap 1.88 (2026-08-26).
!define NPCAP_URL     "https://npcap.com/dist/npcap-1.88.exe"
!define OLLAMA_URL    "https://ollama.com/download/OllamaSetup.exe"

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
    IfFileExists "$WINDIR\System32\Npcap\wpcap.dll" npcap_present 0
    IfFileExists "$WINDIR\System32\wpcap.dll"        npcap_present 0

    DetailPrint "Downloading Npcap (packet capture driver)..."
    SetOutPath "$TEMP"
    inetc::get /CAPTION "Downloading Npcap..." /BANNER "Please wait..." "${NPCAP_URL}" "$TEMP\npcap_setup.exe" /END
    Pop $0
    StrCmp $0 "OK" npcap_install 0
    MessageBox MB_OK "Could not download Npcap (error: $0).$\r$\nInstall it manually from https://npcap.com/ — packet capture will not work without it."
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
    inetc::get /CAPTION "Downloading Wireshark..." /BANNER "Please wait..." "${WIRESHARK_URL}" "$TEMP\wireshark_setup.exe" /END
    Pop $0
    StrCmp $0 "OK" ws_install 0
    MessageBox MB_OK "Could not download Wireshark (error: $0).$\r$\nInstall manually from https://www.wireshark.org/"
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
    inetc::get /CAPTION "Downloading Ollama..." /BANNER "Please wait..." "${OLLAMA_URL}" "$TEMP\OllamaSetup.exe" /END
    Pop $0
    StrCmp $0 "OK" ollama_install 0
    MessageBox MB_OK "Could not download Ollama (error: $0).$\r$\nThe app's AI needs Ollama - install manually from https://ollama.com/"
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
  !insertmacro MUI_DESCRIPTION_TEXT ${SecWireshark} "Wireshark and the Npcap driver — needed for packet capture, live topology and flow analysis. Npcap shows a short wizard (its free build cannot install silently)."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecOllama}    "Ollama runs the AI features locally on this machine. No API key and no cloud account needed."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecClient}    "A standalone client that connects to a Vanguard Flow NetSentinel running on this or another PC and shows its dashboard, alerts, devices, quality, heatmap and outages. Install this on a second machine."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecShortcuts} "Desktop and Start Menu shortcuts."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ── Uninstaller ────────────────────────────────────────────
Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\NetworkMonitorClient.exe"
    Delete "$INSTDIR\bg.jpg"
    Delete "$INSTDIR\speedtest.exe"
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
    MessageBox MB_OK "Vanguard Flow NetSentinel has been uninstalled.$\r$\nWireshark, Npcap and Ollama were NOT removed."
SectionEnd
