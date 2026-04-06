; ClipFinder NSIS Installer
; Shortcuts call pythonw.exe directly

!define APP_NAME    "ClipFinder"
!define APP_VER     "1.1"
!define APP_PUB     "@MarsScumbags"
!define APP_URL     "https://x.com/MarsScumbags"
!define UNINST_KEY  "Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipFinder"
!define INST_KEY    "Software\ClipFinder"

Name "${APP_NAME} ${APP_VER}"
OutFile "ClipFinder_Setup.exe"
InstallDir "$LOCALAPPDATA\ClipFinder"
InstallDirRegKey HKCU "${INST_KEY}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "clipfinder.ico"
!define MUI_UNICON "clipfinder.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Launch ClipFinder"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function LaunchApp
    SetOutPath "$INSTDIR"
    Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\clipfinder.py"'
FunctionEnd

Section "ClipFinder" SecMain
    SectionIn RO
    SetOutPath "$INSTDIR"

    File "ClipFinder_dist\clipfinder.py"
    File "clipfinder.ico"

    SetOutPath "$INSTDIR\python"
    File /r "ClipFinder_dist\python\*.*"

    ; Desktop shortcut
    SetOutPath "$INSTDIR"
    CreateShortcut "$DESKTOP\ClipFinder.lnk" \
        "$INSTDIR\python\pythonw.exe" \
        '"$INSTDIR\clipfinder.py"' \
        "$INSTDIR\clipfinder.ico"

    ; Start Menu
    CreateDirectory "$SMPROGRAMS\ClipFinder"
    CreateShortcut "$SMPROGRAMS\ClipFinder\ClipFinder.lnk" \
        "$INSTDIR\python\pythonw.exe" \
        '"$INSTDIR\clipfinder.py"' \
        "$INSTDIR\clipfinder.ico"
    CreateShortcut "$SMPROGRAMS\ClipFinder\Uninstall.lnk" \
        "$INSTDIR\Uninstall.exe"

    WriteRegStr HKCU "${UNINST_KEY}" "DisplayName"     "ClipFinder"
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion"  "${APP_VER}"
    WriteRegStr HKCU "${UNINST_KEY}" "Publisher"       "${APP_PUB}"
    WriteRegStr HKCU "${UNINST_KEY}" "URLInfoAbout"    "${APP_URL}"
    WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon"     "$INSTDIR\clipfinder.ico"
    WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
    WriteRegStr HKCU "${INST_KEY}" "InstallDir" "$INSTDIR"

    WriteUninstaller "$INSTDIR\Uninstall.exe"

    IfFileExists "$INSTDIR\clipfinder_config.json" 0 FreshInstall
        MessageBox MB_OK|MB_ICONINFORMATION \
            "ClipFinder updated!$\n$\nYour settings and API keys have been preserved."
    FreshInstall:
SectionEnd

Section "Uninstall"
    IfFileExists "$INSTDIR\clipfinder_config.json" 0 RemoveAll
        MessageBox MB_YESNO|MB_ICONQUESTION \
            "Keep your settings and API keys?" \
            IDYES KeepData IDNO RemoveAll

    KeepData:
        RMDir /r "$INSTDIR\python"
        Delete "$INSTDIR\clipfinder.py"
        Delete "$INSTDIR\clipfinder.ico"
        Delete "$INSTDIR\Uninstall.exe"
        Goto CleanShortcuts

    RemoveAll:
        RMDir /r "$INSTDIR"

    CleanShortcuts:
        Delete "$DESKTOP\ClipFinder.lnk"
        Delete "$SMPROGRAMS\ClipFinder\ClipFinder.lnk"
        Delete "$SMPROGRAMS\ClipFinder\Uninstall.lnk"
        RMDir  "$SMPROGRAMS\ClipFinder"
        DeleteRegKey HKCU "${UNINST_KEY}"
        DeleteRegKey HKCU "${INST_KEY}"
SectionEnd
