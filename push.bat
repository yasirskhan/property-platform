@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM push.bat
REM ------------------------------------------------------------
REM One-click Git push for property-platform.
REM
REM Double-click this file (or a desktop shortcut to it).
REM
REM   1. cd into the repo
REM   2. git add .
REM   3. git commit (with a timestamped message)
REM   4. git push
REM
REM If nothing has changed, it still pushes (harmless).
REM ============================================================

set REPO=C:\Projects\property-platform

echo.
echo ============================================================
echo  Property Platform - push to GitHub
echo ============================================================
echo.

cd /d "%REPO%"
if errorlevel 1 (
    echo ERROR: Could not cd into %REPO%
    goto :end
)

REM --- Show what's about to be saved ---------------------------
echo Current status:
git status --short
if errorlevel 1 (
    echo ERROR: git status failed. Is this a git repo?
    goto :end
)
echo.

REM --- Stage everything ----------------------------------------
echo ^>^>^> git add .
git add .
if errorlevel 1 (
    echo ERROR: git add failed.
    goto :end
)

REM --- Commit --------------------------------------------------
set MSG=auto-push %DATE% %TIME%
echo ^>^>^> git commit -m "%MSG%"
git commit -m "%MSG%"
REM (commit returns non-zero when there is nothing to commit; ignore)

REM --- Push ----------------------------------------------------
echo.
echo ^>^>^> git push
git push
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  PUSH FAILED. Read the error above.
    echo ============================================================
    goto :end
)

echo.
echo ============================================================
echo  DONE. Everything is on GitHub.
echo ============================================================

:end
echo.
echo Press any key to close...
pause >nul
endlocal