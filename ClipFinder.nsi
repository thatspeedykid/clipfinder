; ============================================================
; ClipFinder v1.3.2 — NSIS Installer
; Lightweight — no bundled packages.
; All packages download automatically on first launch.
; ============================================================

!define APP_NAME     "ClipFinder"
!define APP_VERSION  "1.3.2"
!define APP_EXE      "clipfinder.exe"
!define INSTALL_DIR  "$LOCALAPPDATA\ClipFinder"
!define PUBLISHER    "MarsScumbags"
!define WEBSITE      "https://github.com/thatspeedykid/clipfinder"

Name          "${APP_NAME} ${APP_VERSION}"
OutFile       "ClipFinder-Setup.exe"
InstallDir    "${INSTALL_DIR}"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Unicode       True

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON   "clipfinder.ico"
!define MUI_UNICON "clipfinder.ico"
!define MUI_WELCOMEPAGE_TITLE    "Install ClipFinder ${APP_VERSION}"
!define MUI_WELCOMEPAGE_TEXT     "ClipFinder is an AI-powered drama clip extractor.$\n$\nRequired packages (torch, whisper, demucs, etc.) download automatically on first launch.$\n$\nYou will need an internet connection on first run."
!define MUI_FINISHPAGE_RUN       "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT  "Launch ClipFinder now"
!define MUI_FINISHPAGE_LINK      "Visit GitHub for updates"
!define MUI_FINISHPAGE_LINK_LOCATION "${WEBSITE}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "ClipFinder" SecMain
    SectionIn RO
    SetOutPath "$INSTDIR"
    File "ClipFinder_dist\clipfinder.exe"
    File "ClipFinder_dist\clipfinder.ico"
    File "ClipFinder_dist\clipfinder.py"
    File "ClipFinder_dist\README.md"
    File "ClipFinder_dist\CHANGELOG.md"

    SetOutPath "$INSTDIR\python"
    File /r "ClipFinder_dist\python\*.*"

    ; Fresh install — delete stamp so packages install on first launch
    Delete "$INSTDIR\install_done.stamp"
    Delete "$INSTDIR\pending_update.flag"
    CreateDirectory "$INSTDIR\pkgs"

    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\clipfinder.ico"
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\clipfinder.ico"

    WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName"     "${APP_NAME} ${APP_VERSION}"
    WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher"       "${PUBLISHER}"
    WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon"     "$INSTDIR\clipfinder.ico"
    WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "URLInfoAbout"    "${WEBSITE}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\clipfinder.exe"
    Delete "$INSTDIR\clipfinder.py"
    Delete "$INSTDIR\clipfinder.ico"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\CHANGELOG.md"
    Delete "$INSTDIR\Uninstall.exe"
    Delete "$INSTDIR\install_done.stamp"
    Delete "$INSTDIR\pending_update.flag"
    RMDir /r "$INSTDIR\python"
    RMDir /r "$INSTDIR\pkgs"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    ; Config and clips preserved — user can delete $LOCALAPPDATA\ClipFinder manually
SectionEnd
