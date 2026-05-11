@echo off
setlocal EnableDelayedExpansion
set PIP_DISABLE_PIP_VERSION_CHECK=1
title ClipFinder — Build Installer

echo ============================================
echo   ClipFinder Installer Builder v1.3.7.1
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
echo [1/5] Downloading Python 3.12 embeddable...
py -3.12 setup_embed.py
if errorlevel 1 ( echo [ERROR] Step 1 failed & pause & exit /b 1 )
echo     OK

:: Step 2: pip into embedded Python
echo.
echo [2/5] Installing pip into embedded Python...
py -3.12 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py','_getpip.py')"
ClipFinder_dist\python\python.exe _getpip.py --quiet
del _getpip.py
echo     OK

:: Step 2b: Pre-install faster-whisper, demucs + torch into pkgs folder
:: These are the packages that fail on fresh Windows — bundle them
echo.
echo [2b/5] Pre-installing faster-whisper + demucs into bundled pkgs...
echo   (This downloads ~2GB — torch CPU wheels + faster-whisper + demucs)
echo   This step takes 5-15 minutes depending on your connection.
echo.
mkdir "ClipFinder_dist\pkgs"

:: torch CPU — reliable, no CUDA needed, works on all Windows
echo   [1/4] torch (CPU)...
ClipFinder_dist\python\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --target ClipFinder_dist\pkgs --quiet --no-warn-script-location
if errorlevel 1 (
    echo   [WARN] torch install failed - will install at runtime
) else (
    echo   [OK] torch
)

:: faster-whisper
echo   [2/4] faster-whisper...
ClipFinder_dist\python\python.exe -m pip install faster-whisper --target ClipFinder_dist\pkgs --quiet --no-warn-script-location
if errorlevel 1 (
    echo   [WARN] faster-whisper install failed - will install at runtime
) else (
    echo   [OK] faster-whisper
)

:: openai-whisper (fallback)
echo   [3/4] openai-whisper...
ClipFinder_dist\python\python.exe -m pip install openai-whisper --target ClipFinder_dist\pkgs --quiet --no-warn-script-location
if errorlevel 1 (
    echo   [WARN] openai-whisper install failed - will install at runtime
) else (
    echo   [OK] openai-whisper
)

:: demucs
echo   [4/4] demucs...
ClipFinder_dist\python\python.exe -m pip install demucs --target ClipFinder_dist\pkgs --quiet --no-warn-script-location
if errorlevel 1 (
    echo   [WARN] demucs install failed - will install at runtime
) else (
    echo   [OK] demucs
)

echo     Pre-install step done.

:: Step 3: Copy app files + build launcher EXE
echo.
echo [3/5] Building launcher + packaging app...
copy "clipfinder.py"       "ClipFinder_dist\clipfinder.py"       >nul
copy "clipfinder_core.py"  "ClipFinder_dist\clipfinder_core.py"  >nul
if exist "clipfinder.ico"  copy "clipfinder.ico"  "ClipFinder_dist\clipfinder.ico"  >nul
if exist "preview.webp"    copy "preview.webp"    "ClipFinder_dist\preview.webp"    >nul
copy "README.md"    "ClipFinder_dist\README.md"    >nul 2>&1
copy "CHANGELOG.md" "ClipFinder_dist\CHANGELOG.md" >nul 2>&1

:: vision_refs
if exist "vision_refs" (
    mkdir "ClipFinder_dist\vision_refs"
    xcopy /s /q "vision_refs\*" "ClipFinder_dist\vision_refs\" >nul 2>&1
)

py -3.12 -m pip install pyinstaller --quiet
py -3.12 build_launcher.py
if errorlevel 1 ( echo [ERROR] Launcher build failed & pause & exit /b 1 )
echo     OK

:: Step 4: Compile NSIS installer
echo.
echo [4/5] Compiling NSIS installer...

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
