@echo off
setlocal EnableDelayedExpansion
set PIP_DISABLE_PIP_VERSION_CHECK=1
title ClipFinder — Make Installer

echo ============================================
echo   ClipFinder Installer Compiler
echo   Requires: ClipFinder_dist\ + NSIS
echo ============================================
echo.

:: Check ClipFinder_dist exists
if not exist "ClipFinder_dist\python\python.exe" (
    echo [ERROR] ClipFinder_dist\python\python.exe not found.
    echo Run setup_build.py first:  py -3.12 setup_build.py
    pause & exit /b 1
)
if not exist "ClipFinder_dist\clipfinder.py" (
    echo [ERROR] ClipFinder_dist\clipfinder.py not found.
    echo Run setup_build.py first:  py -3.12 setup_build.py
    pause & exit /b 1
)
echo [OK] ClipFinder_dist\ looks good.
echo.

:: Find NSIS
set NSIS=
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set NSIS=C:\Program Files (x86)\NSIS\makensis.exe
if exist "C:\Program Files\NSIS\makensis.exe"       set NSIS=C:\Program Files\NSIS\makensis.exe

if "%NSIS%"=="" (
    echo [ERROR] NSIS not found.
    echo Install from: https://nsis.sourceforge.io/Download
    pause & exit /b 1
)
echo [OK] NSIS found.
echo.

:: Compile
echo Compiling installer...
"%NSIS%" installer.nsi
if errorlevel 1 (
    echo [ERROR] NSIS compilation failed.
    pause & exit /b 1
)

:: Done
echo.
if exist "ClipFinder_Setup.exe" (
    for %%F in ("ClipFinder_Setup.exe") do set SZ=%%~zF
    set /a MB=!SZ! / 1048576
    echo ============================================
    echo   ClipFinder_Setup.exe  ^(!MB! MB^)
    echo   Ready to distribute!
    echo ============================================
    choice /M "Open folder?"
    if not errorlevel 2 explorer .
) else (
    echo [ERROR] Setup EXE not created.
)
pause
endlocal
