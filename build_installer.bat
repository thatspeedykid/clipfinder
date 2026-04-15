@echo off
setlocal EnableDelayedExpansion
set PIP_DISABLE_PIP_VERSION_CHECK=1
title ClipFinder — Build Installer

echo ============================================
echo   ClipFinder Installer Builder
echo   Output: ClipFinder-Setup.exe
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
echo [1/4] Downloading Python 3.12 embeddable...
py -3.12 setup_embed.py
if errorlevel 1 ( echo [ERROR] Step 1 failed & pause & exit /b 1 )
echo     OK

:: Step 2: pip only (no packages — app installs them on first launch)
echo.
echo [2/4] Installing pip into embedded Python...
py -3.12 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py','_getpip.py')"
ClipFinder_dist\python\python.exe _getpip.py --quiet
del _getpip.py
echo     OK

:: Step 3: Copy app files + build launcher EXE
echo.
echo [3/4] Building launcher + packaging app...
copy "clipfinder.py"  "ClipFinder_dist\clipfinder.py"  >nul
if exist "clipfinder.ico" copy "clipfinder.ico" "ClipFinder_dist\clipfinder.ico" >nul
if exist "preview.webp"   copy "preview.webp"   "ClipFinder_dist\preview.webp"   >nul
copy "README.md"    "ClipFinder_dist\README.md"    >nul 2>&1
copy "CHANGELOG.md" "ClipFinder_dist\CHANGELOG.md" >nul 2>&1

py -3.12 -m pip install pyinstaller --quiet
py -3.12 build_launcher.py
if errorlevel 1 ( echo [ERROR] Launcher build failed & pause & exit /b 1 )
echo     OK

:: Step 4: Compile NSIS installer
echo.
echo [4/4] Compiling NSIS installer...

set NSIS=""
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set NSIS="C:\Program Files (x86)\NSIS\makensis.exe"
if exist "C:\Program Files\NSIS\makensis.exe"       set NSIS="C:\Program Files\NSIS\makensis.exe"

if %NSIS%=="" (
    echo [!] NSIS not found — skipping.
    goto done
)

%NSIS% ClipFinder.nsi
if errorlevel 1 ( echo [ERROR] NSIS compilation failed & pause & exit /b 1 )
echo     OK

:done
echo.
echo ============================================
if exist "ClipFinder-Setup.exe" (
    for %%F in ("ClipFinder-Setup.exe") do set SZ=%%~zF
    set /a SMB=!SZ! / 1048576
    echo   ClipFinder-Setup.exe  ^(!SMB! MB^)
) else (
    echo   ClipFinder_dist\ folder ready.
)
echo ============================================
echo.
pause
endlocal
