@echo off
setlocal EnableDelayedExpansion
set PIP_DISABLE_PIP_VERSION_CHECK=1
title ClipFinder - Build Installer

:: Which Python builds everything. Locally: the py launcher. CI sets PYEXE=python (the
:: setup-python interpreter) so embed version, tkinter source and launcher all come from one place.
if not defined PYEXE set "PYEXE=py -3.12"

echo ============================================
echo   ClipFinder Installer Builder
echo   Output: ClipFinder-Setup.exe
echo ============================================
echo.

%PYEXE% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.12 required ^(PYEXE=%PYEXE%^).
    (if not defined CI pause) & exit /b 1
)
for /f "tokens=*" %%V in ('%PYEXE% --version 2^>^&1') do echo [OK] %%V
echo.

:: Clean
if exist "ClipFinder_dist" rmdir /s /q "ClipFinder_dist"
mkdir "ClipFinder_dist"

:: Step 1: Embedded Python
echo [1/4] Downloading Python 3.12 embeddable...
%PYEXE% setup_embed.py
if errorlevel 1 ( echo [ERROR] Step 1 failed & (if not defined CI pause) & exit /b 1 )
echo     OK

:: Step 2: pip into embedded Python
echo.
echo [2/4] Installing pip into embedded Python...
%PYEXE% -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py','_getpip.py')"
if errorlevel 1 ( echo [ERROR] get-pip.py download failed & (if not defined CI pause) & exit /b 1 )
ClipFinder_dist\python\python.exe _getpip.py --quiet
if errorlevel 1 ( echo [ERROR] get-pip.py install failed & del _getpip.py & (if not defined CI pause) & exit /b 1 )
del _getpip.py
:: Create pkgs folder - workflow will fill it with pre-built packages
mkdir "ClipFinder_dist\pkgs"
echo     OK

:: Step 3: Copy app files + build launcher EXE
echo.
echo [3/4] Building launcher + packaging app...
copy "clipfinder.py"       "ClipFinder_dist\clipfinder.py"       >nul || goto :copyfail
if exist "clipfinder.ico"  copy "clipfinder.ico"  "ClipFinder_dist\clipfinder.ico"  >nul
if exist "preview.webp"    copy "preview.webp"    "ClipFinder_dist\preview.webp"    >nul
if exist "assets\clipfinder_logo_512.png"  copy "assets\clipfinder_logo_512.png"  "ClipFinder_dist\clipfinder_logo_512.png"  >nul

:: Bundle VLC DLLs so users don't need VLC installed separately.
:: NOTE: never put an unquoted %VLC_SRC% (contains "(x86)") inside a ( ) block - the ")" ends the
:: block. Use !VLC_SRC! (delayed expansion) there.
echo Bundling VLC DLLs...
set "VLC_SRC="
if exist "C:\Program Files (x86)\VideoLAN\VLC\libvlc.dll" set "VLC_SRC=C:\Program Files (x86)\VideoLAN\VLC"
:: 64-bit VLC must win (the app runs 64-bit Python); it is checked last so it overrides the x86 one
if exist "C:\Program Files\VideoLAN\VLC\libvlc.dll"       set "VLC_SRC=C:\Program Files\VideoLAN\VLC"
if exist "ClipFinder_dist\vlc\libvlc.dll" (
    echo     VLC already bundled
) else if defined VLC_SRC (
    mkdir "ClipFinder_dist\vlc" 2>nul
    copy "!VLC_SRC!\libvlc.dll"     "ClipFinder_dist\vlc\" >nul 2>&1
    copy "!VLC_SRC!\libvlccore.dll" "ClipFinder_dist\vlc\" >nul 2>&1
    xcopy /s /q "!VLC_SRC!\plugins" "ClipFinder_dist\vlc\plugins\" >nul 2>&1
    echo     VLC bundled from !VLC_SRC!
) else (
    echo     WARNING: VLC not found - Editor tab player will require VLC installed by user
)
copy "README.md"    "ClipFinder_dist\README.md"    >nul || goto :copyfail
copy "CHANGELOG.md" "ClipFinder_dist\CHANGELOG.md" >nul || goto :copyfail

:: vision_refs
if exist "vision_refs" (
    mkdir "ClipFinder_dist\vision_refs"
    xcopy /s /q "vision_refs\*" "ClipFinder_dist\vision_refs\" >nul 2>&1
)

%PYEXE% -m pip install pyinstaller==6.22.3 --quiet
if errorlevel 1 ( echo [ERROR] pip install pyinstaller failed & (if not defined CI pause) & exit /b 1 )
%PYEXE% build_launcher.py
if errorlevel 1 ( echo [ERROR] Launcher build failed & (if not defined CI pause) & exit /b 1 )
echo     OK

:: Step 4: NSIS - called separately by workflow after packages are pre-installed
echo.
echo [4/4] Build complete. NSIS will be compiled by workflow after package install.
echo     (If running locally, run: makensis ClipFinder.nsi)
echo     OK

echo.
echo ============================================
echo   ClipFinder_dist\ ready
echo ============================================
echo.
endlocal
exit /b 0

:copyfail
echo [ERROR] Could not copy a required file into ClipFinder_dist
(if not defined CI pause) & exit /b 1
