@echo off
REM ============================================================
REM push.bat
REM ------------------------------------------------------------
REM One-click Git push for property-platform.
REM
REM Double-click this file (or a desktop shortcut to it).
REM It will:
REM   1. cd into the repo
REM   2. git add .
REM   3. git commit with a timestamped message
REM   4. git push
REM
REM If nothing has changed, it just pushes anyway (harmless).
REM ============================================================

setlocal

set REPO=C:\Projects\property-platform
set MSG=auto-push %DATE% %TIME%

cd /d "%REPO%"
if errorlevel 1 (
    echo.
    echo ERROR: Could not cd into %REPO%
    echo Check that the folder exists.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Pushing property-platform
echo  Repo:    %REPO%
echo  Message: %MSG%
echo ============================================================
echo.

echo ^> git add .
git add .
if errorlevel 1 goto :fail

echo.
echo ^> git commit
git commit -m "%MSG%"
REM Note: a non-zero exit here usually just means "nothing to commit".
REM We do NOT stop — we still push in case the branch is behind.

echo.
echo ^> git push
git push
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  DONE. Everything is on GitHub.
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo  FAILED. Read the error above.
echo ============================================================
echo.
pause
exit /b 1