@echo off
setlocal EnableDelayedExpansion
set PIP_DISABLE_PIP_VERSION_CHECK=1
title ClipFinder Build

echo ============================================
echo   ClipFinder Installer Builder
echo   Output: ClipFinder_Setup.exe
echo   Installs to Program Files + shortcuts
echo ============================================
echo.

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.12 required.
    pause & exit /b 1
)
for /f "tokens=*" %%V in ('py -3.12 --version 2^>^&1') do echo [OK] %%V
echo.

:: Clean
if exist "ClipFinder_dist" rmdir /s /q "ClipFinder_dist"
mkdir "ClipFinder_dist"

:: Step 1: Embedded Python
echo [1/5] Downloading Python 3.12 embeddable...
py -3.12 setup_embed.py
if errorlevel 1 ( echo [ERROR] Step 1 failed & exit /b 1 )
echo     OK

:: Step 2: pip
echo.
echo [2/5] Installing pip into embedded Python...
py -3.12 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py','_getpip.py')"
ClipFinder_dist\python\python.exe _getpip.py --quiet
del _getpip.py

:: CRITICAL: setuptools + wheel must be first or source packages fail
set PY=ClipFinder_dist\python\python.exe
%PY% -m pip install setuptools wheel --quiet --upgrade --no-warn-script-location
echo     OK

:: Step 3: All packages
echo.
echo [3/5] Installing all packages (10-20 min first time)...

echo   AI providers...
%PY% -m pip install google-genai groq openai requests --quiet --upgrade --no-warn-script-location

echo   Downloader...
%PY% -m pip install yt-dlp curl-cffi --quiet --upgrade --no-warn-script-location

echo   Numeric base...
%PY% -m pip install numpy scipy --quiet --upgrade --no-warn-script-location

echo   Whisper...
%PY% -m pip install faster-whisper openai-whisper --quiet --upgrade --no-warn-script-location

echo   Image + video...
%PY% -m pip install Pillow imagehash opencv-python --quiet --upgrade --no-warn-script-location

echo   Audio...
%PY% -m pip install soundfile --quiet --upgrade --no-warn-script-location

echo   Optional (face tracking)...
%PY% -m pip install mediapipe --quiet --upgrade --no-deps --no-warn-script-location
echo     OK

:: Step 4: Copy app files
echo.
echo [4/5] Copying app files...
copy "clipfinder.py"  "ClipFinder_dist\clipfinder.py"  >nul
if exist "clipfinder.ico" copy "clipfinder.ico" "ClipFinder_dist\clipfinder.ico" >nul
if exist "preview.webp"   copy "preview.webp"   "ClipFinder_dist\preview.webp"   >nul
echo     OK

:: Step 5: Compile NSIS
echo.
echo [5/5] Compiling NSIS installer...
set NSIS=
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set NSIS=C:\Program Files (x86)\NSIS\makensis.exe
if exist "C:\Program Files\NSIS\makensis.exe"       set NSIS=C:\Program Files\NSIS\makensis.exe

if "%NSIS%"=="" (
    echo [!] NSIS not found - skipping
    goto done
)

"%NSIS%" installer.nsi
if errorlevel 1 ( echo [ERROR] NSIS compilation failed & exit /b 1 )
echo     OK

:done
echo.
if exist "ClipFinder_Setup.exe" (
    for %%F in ("ClipFinder_Setup.exe") do set SZ=%%~zF
    set /a MB=!SZ! / 1048576
    echo ============================================
    echo   ClipFinder_Setup.exe  ^(!MB! MB^)
    echo   Ready to distribute!
    echo ============================================
) else (
    echo [ERROR] Setup EXE not created.
    exit /b 1
)
endlocal
