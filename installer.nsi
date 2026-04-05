; ClipFinder NSIS Installer Script

!define APP_NAME "ClipFinder"
!define APP_VERSION "1.0"
!define APP_PUBLISHER "@MarsScumbags"
!define APP_URL "https://x.com/MarsScumbags"
!define UNINSTALL_REG "Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipFinder"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "ClipFinder_Setup.exe"
InstallDir "$PROGRAMFILES64\ClipFinder"
InstallDirRegKey HKLM "Software\ClipFinder" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
ShowInstDetails show

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "clipfinder.ico"
!define MUI_UNICON "clipfinder.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\ClipFinder.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ClipFinder"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "ClipFinder" SecMain
    SectionIn RO

    SetOutPath "$INSTDIR"

    ; Main app files — always overwrite
    File "ClipFinder_dist\ClipFinder.exe"
    File "ClipFinder_dist\clipfinder.py"
    File "clipfinder.ico"

    ; Embedded Python
    SetOutPath "$INSTDIR\python"
    File /r "ClipFinder_dist\python\*.*"

    ; ── Preserve user data on updates ────────────────────────────────────────
    ; Only copy these if they don't already exist (first install only)
    ; On updates, existing files are left untouched so user settings survive.
    SetOutPath "$INSTDIR"
    SetOverwrite off
        ; Config file — never overwrite, user's settings stay intact
        ; (file doesn't exist in dist, this just ensures the flag is set)
    SetOverwrite on

    ; Desktop shortcut
    CreateShortcut "$DESKTOP\ClipFinder.lnk" "$INSTDIR\ClipFinder.exe" "" "$INSTDIR\clipfinder.ico" 0 SW_SHOWNORMAL "" "ClipFinder - AI Drama Clip Extractor"

    ; Start Menu
    CreateDirectory "$SMPROGRAMS\ClipFinder"
    CreateShortcut "$SMPROGRAMS\ClipFinder\ClipFinder.lnk" "$INSTDIR\ClipFinder.exe" "" "$INSTDIR\clipfinder.ico" 0
    CreateShortcut "$SMPROGRAMS\ClipFinder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

    ; Registry
    WriteRegStr HKLM "${UNINSTALL_REG}" "DisplayName"     "ClipFinder"
    WriteRegStr HKLM "${UNINSTALL_REG}" "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr HKLM "${UNINSTALL_REG}" "Publisher"       "${APP_PUBLISHER}"
    WriteRegStr HKLM "${UNINSTALL_REG}" "URLInfoAbout"    "${APP_URL}"
    WriteRegStr HKLM "${UNINSTALL_REG}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "${UNINSTALL_REG}" "DisplayIcon"     "$INSTDIR\clipfinder.ico"
    WriteRegStr HKLM "${UNINSTALL_REG}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegDWORD HKLM "${UNINSTALL_REG}" "NoModify" 1
    WriteRegDWORD HKLM "${UNINSTALL_REG}" "NoRepair" 1
    WriteRegStr HKLM "Software\ClipFinder" "InstallDir" "$INSTDIR"

    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; ── Show update notice if upgrading ──────────────────────────────────────
    IfFileExists "$INSTDIR\clipfinder_config.json" IsUpdate FreshInstall
    IsUpdate:
        MessageBox MB_OK|MB_ICONINFORMATION \
            "ClipFinder updated successfully!$\n$\nYour settings and API keys have been preserved.$\nffmpeg, whisper models, and pkgs\ folder untouched."
        Goto Done
    FreshInstall:
        ; Nothing extra needed on fresh install
    Done:
SectionEnd

Section "Uninstall"
    ; ── Preserve user data on uninstall ──────────────────────────────────────
    ; Back up config before removing (or just leave it)
    IfFileExists "$INSTDIR\clipfinder_config.json" 0 +2
        MessageBox MB_YESNO|MB_ICONQUESTION \
            "Keep your settings and API keys?$\n$\n(clipfinder_config.json and pkgs\ folder)" \
            IDYES KeepData IDNO RemoveAll

    KeepData:
        ; Remove app files but leave user data
        Delete "$INSTDIR\ClipFinder.exe"
        Delete "$INSTDIR\clipfinder.py"
        Delete "$INSTDIR\clipfinder.ico"
        Delete "$INSTDIR\Uninstall.exe"
        RMDir /r "$INSTDIR\python"
        ; Leave: clipfinder_config.json, pkgs\, whisper_cpp\, ffmpeg_bin\, whisper_models\
        Goto CleanShortcuts

    RemoveAll:
        RMDir /r "$INSTDIR"

    CleanShortcuts:
        Delete "$DESKTOP\ClipFinder.lnk"
        Delete "$SMPROGRAMS\ClipFinder\ClipFinder.lnk"
        Delete "$SMPROGRAMS\ClipFinder\Uninstall.lnk"
        RMDir "$SMPROGRAMS\ClipFinder"
        DeleteRegKey HKLM "${UNINSTALL_REG}"
        DeleteRegKey HKLM "Software\ClipFinder"
SectionEnd
