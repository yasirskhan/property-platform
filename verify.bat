@echo off
setlocal
cd /d "%~dp0"
if exist "backend\venv\Scripts\python.exe" (
  "backend\venv\Scripts\python.exe" verify_project.py
) else (
  python verify_project.py
)
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" echo Verification failed with exit code %EXITCODE%.
if "%EXITCODE%"=="0" echo Verification passed.
pause
exit /b %EXITCODE%
