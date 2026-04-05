@echo off
setlocal EnableDelayedExpansion
set PIP_DISABLE_PIP_VERSION_CHECK=1
title ClipFinder — Build Installer

echo ============================================
echo   ClipFinder Installer Builder
echo   Output: ClipFinder_Setup.exe
echo   Installs to Program Files + shortcuts
echo ============================================
echo.

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.12 required.
    echo Get it: https://www.python.org/downloads/release/python-3127/
    pause & exit /b 1
)
for /f "tokens=*" %%V in ('py -3.12 --version 2^>^&1') do echo [OK] %%V
echo.

:: Clean
if exist "ClipFinder_dist" rmdir /s /q "ClipFinder_dist"
mkdir "ClipFinder_dist"

:: ── Step 1: Embedded Python ───────────────────────────────────────────────────
echo [1/5] Downloading Python 3.12 embeddable...
py -3.12 setup_embed.py
if errorlevel 1 ( echo [ERROR] Step 1 failed & pause & exit /b 1 )
echo     OK

:: ── Step 2: pip ───────────────────────────────────────────────────────────────
echo.
echo [2/5] Installing pip into embedded Python...
py -3.12 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py','_getpip.py')"
ClipFinder_dist\python\python.exe _getpip.py --quiet
del _getpip.py
echo     OK

:: ── Step 3: All packages ──────────────────────────────────────────────────────
echo.
echo [3/5] Installing all packages (10-20 min first time)...
set PY=ClipFinder_dist\python\python.exe

echo   AI providers...
%PY% -m pip install google-genai groq openai --quiet --upgrade --no-warn-script-location
echo   Whisper...
%PY% -m pip install faster-whisper --quiet --upgrade --no-deps --no-warn-script-location
%PY% -m pip install faster-whisper openai-whisper --quiet --upgrade --no-warn-script-location
echo   Video + image...
%PY% -m pip install yt-dlp curl-cffi Pillow opencv-python imagehash --quiet --upgrade --no-warn-script-location
echo   Audio + numeric...
%PY% -m pip install numpy soundfile requests --quiet --upgrade --no-warn-script-location
echo   Optional (face tracking)...
%PY% -m pip install mediapipe --quiet --upgrade --no-deps --no-warn-script-location
echo     OK

:: ── Step 4: Copy app + build launcher EXE ────────────────────────────────────
echo.
echo [4/5] Building launcher + packaging app...
copy "clipfinder.py"  "ClipFinder_dist\clipfinder.py"  >nul
if exist "clipfinder.ico" copy "clipfinder.ico" "ClipFinder_dist\clipfinder.ico" >nul
if exist "preview.webp"   copy "preview.webp"   "ClipFinder_dist\preview.webp"   >nul

py -3.12 -m pip install pyinstaller --quiet
py -3.12 build_launcher.py
if errorlevel 1 ( echo [ERROR] Launcher build failed & pause & exit /b 1 )
echo     OK

:: ── Step 5: Compile NSIS installer ───────────────────────────────────────────
echo.
echo [5/5] Compiling NSIS installer...

:: Find NSIS
set NSIS=""
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set NSIS="C:\Program Files (x86)\NSIS\makensis.exe"
if exist "C:\Program Files\NSIS\makensis.exe"       set NSIS="C:\Program Files\NSIS\makensis.exe"

if %NSIS%=="" (
    echo.
    echo [!] NSIS not found — skipping installer compilation.
    echo     Install NSIS from: https://nsis.sourceforge.io/Download
    echo     Then re-run this script to get ClipFinder_Setup.exe
    echo.
    echo     For now, distribute the ClipFinder_dist\ folder directly.
    goto done
)

%NSIS% installer.nsi
if errorlevel 1 ( echo [ERROR] NSIS compilation failed & pause & exit /b 1 )
echo     OK

:done
echo.
echo ============================================
if exist "ClipFinder_Setup.exe" (
    for %%F in ("ClipFinder_Setup.exe") do set SZ=%%~zF
    set /a SMB=!SZ! / 1048576
    echo   ClipFinder_Setup.exe  ^(!SMB! MB^)
    echo.
    echo   Users double-click to install.
    echo   Installs to Program Files\ClipFinder
    echo   Desktop + Start Menu shortcuts added.
    echo   Proper uninstaller included.
) else (
    echo   ClipFinder_dist\ folder ready to distribute.
    echo   Install NSIS to compile a proper Setup.exe
)
echo ============================================
echo.
choice /M "Open output folder?"
if not errorlevel 2 (
    if exist "ClipFinder_Setup.exe" explorer .
    if not exist "ClipFinder_Setup.exe" explorer ClipFinder_dist
)
pause
endlocal
