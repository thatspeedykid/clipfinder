; ============================================================
; ClipFinder - NSIS Installer
;
; APP_VERSION is the release version. It is NOT regex-patched at build time any more:
;   - `python tools/release_version.py set X.Y.Z.W` writes it (asserted: exactly one match)
;   - CI runs `tools/release_version.py check --tag <tag>` and fails the build on any mismatch
;   - CI then reads the version back out of the built ClipFinder-Setup.exe and fails if it differs
; Rules: keep it ONE line `!define APP_VERSION "X.Y.Z.W"` with exactly 4 numbers (VIProductVersion
; needs that), and keep this whole file pure ASCII (NSIS reads it as ANSI, so a non-ASCII
; character such as an em dash turns into mojibake in the installer).
; ============================================================

!define APP_NAME     "ClipFinder"
!define APP_VERSION "1.4.0.0"
!define APP_EXE      "clipfinder.exe"
!define INSTALL_DIR  "$LOCALAPPDATA\ClipFinder"
!define PUBLISHER    "MarsScumbags"
!define WEBSITE      "https://github.com/thatspeedykid/clipfinder"

Name          "${APP_NAME} ${APP_VERSION}"
BrandingText  "${APP_NAME} ${APP_VERSION}"
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
!define MUI_WELCOMEPAGE_TEXT     "ClipFinder is an AI-powered drama clip extractor.$\n$\nThe downloader, AI providers and faster-whisper transcription are pre-bundled - works immediately after install. Optional extras (music removal, OpenAI Whisper) are installed on demand from inside the app."
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

; Version resource of ClipFinder-Setup.exe (Explorer -> Properties -> Details).
; Must come after MUI_LANGUAGE (defines LANG_ENGLISH). VIProductVersion needs X.X.X.X.
VIProductVersion "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductName"      "${APP_NAME}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "CompanyName"      "${PUBLISHER}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileDescription"  "${APP_NAME} Installer"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileVersion"      "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductVersion"   "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "OriginalFilename" "ClipFinder-Setup.exe"
VIAddVersionKey /LANG=${LANG_ENGLISH} "LegalCopyright"   "Copyright (c) ${PUBLISHER}"

Section "ClipFinder" SecMain
    SectionIn RO

    ; Upgrade in place: File /r only adds/overwrites, so the python and vlc trees of a previous
    ; install would be merged with the new ones (stale DLLs / .pyd). Remove what the installer owns
    ; first, but ONLY when a previous ClipFinder install is really in $INSTDIR (the user may have
    ; picked an unrelated folder). Never touched here: config, models, envs, downloads, and
    ; %LOCALAPPDATA%\ClipFinder\pkgs (the app keeps those packages current on its own).
    IfFileExists "$INSTDIR\clipfinder.py" 0 no_previous_install
        RMDir /r "$INSTDIR\python"
        RMDir /r "$INSTDIR\vlc"
        RMDir /r "$INSTDIR\__pycache__"
    no_previous_install:
    ; clipfinder_core.py was retired - remove the copy an older install left behind
    Delete "$INSTDIR\clipfinder_core.py"

    SetOutPath "$INSTDIR"
    File "ClipFinder_dist\clipfinder.exe"
    File "ClipFinder_dist\clipfinder.ico"
    File "ClipFinder_dist\clipfinder.py"
    File "ClipFinder_dist\README.md"
    File "ClipFinder_dist\CHANGELOG.md"
    File "ClipFinder_dist\clipfinder_logo_512.png"

    ; Embedded Python
    SetOutPath "$INSTDIR\python"
    File /r "ClipFinder_dist\python\*.*"

    ; Pre-built packages (one pip transaction, see requirements.txt): yt-dlp, AI SDKs, faster-whisper, OpenCV, ...
    SetOutPath "$LOCALAPPDATA\ClipFinder\pkgs"
    File /r "ClipFinder_dist\pkgs\*.*"

    ; Default vision reference images
    SetOutPath "$LOCALAPPDATA\ClipFinder\vision_refs"
    File /nonfatal "ClipFinder_dist\vision_refs\stake_casino.png"
    File /nonfatal "ClipFinder_dist\vision_refs\roobet_casino.png"
    File /nonfatal "ClipFinder_dist\vision_refs\rainbet_casino.png"

    ; Bundled VLC DLLs - enables Editor tab player without separate VLC install
    SetOutPath "$INSTDIR\vlc"
    File /nonfatal /r "ClipFinder_dist\vlc\*.*"

    SetOutPath "$INSTDIR"

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
    Delete "$INSTDIR\clipfinder_core.py"
    Delete "$INSTDIR\clipfinder.ico"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\CHANGELOG.md"
    Delete "$INSTDIR\clipfinder_logo_512.png"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR\__pycache__"
    RMDir /r "$INSTDIR\python"
    RMDir /r "$INSTDIR\vlc"

    ; Runtime data the installer/app creates under %LOCALAPPDATA%\ClipFinder. All of it is
    ; regenerable, so it is removed (otherwise GBs are orphaned). NOT removed: the user's
    ; settings/API keys (clipfinder_config.json), downloaded models/tools, and their clips.
    RMDir /r "$LOCALAPPDATA\ClipFinder\pkgs"
    RMDir /r "$LOCALAPPDATA\ClipFinder\pkgs_staging"
    RMDir /r "$LOCALAPPDATA\ClipFinder\pkgs_backup"
    RMDir /r "$LOCALAPPDATA\ClipFinder\envs"
    RMDir /r "$LOCALAPPDATA\ClipFinder\kick_thumbs"
    Delete "$LOCALAPPDATA\ClipFinder\update.log"
    ; legacy first-run markers (older versions kept them in $INSTDIR, or in USER_DIR)
    Delete "$INSTDIR\install_done.stamp"
    Delete "$INSTDIR\pending_update.flag"
    Delete "$LOCALAPPDATA\ClipFinder\install_done.stamp"
    Delete "$LOCALAPPDATA\ClipFinder\pending_update.flag"
    Delete "$LOCALAPPDATA\ClipFinder\version.stamp"
    ; default vision references shipped by the installer (user-added ones are kept: RMDir is non-recursive)
    Delete "$LOCALAPPDATA\ClipFinder\vision_refs\stake_casino.png"
    Delete "$LOCALAPPDATA\ClipFinder\vision_refs\roobet_casino.png"
    Delete "$LOCALAPPDATA\ClipFinder\vision_refs\rainbet_casino.png"
    RMDir  "$LOCALAPPDATA\ClipFinder\vision_refs"

    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

    ; Non-recursive on purpose: only succeeds when nothing of the user's is left inside.
    ; (the current directory of the uninstaller can not be removed, so leave it first)
    SetOutPath "$TEMP"
    RMDir "$INSTDIR"
    RMDir "$LOCALAPPDATA\ClipFinder"
SectionEnd
