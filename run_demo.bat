@echo off
rem Lantern POC: one-click demo. Installs, tests, runs the offline demo, then the LIVE Gemini demo.
rem Usage:  run_demo.bat            (live run on the drone scenarios)
rem         run_demo.bat all        (live run on all 12 scenarios)
rem         run_demo.bat m | l | d  (manufacturing, logistics or drone scenarios only)
rem Needs a GEMINI_API_KEY in .env (see .env.example). Uses only the fictional sample images.
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

rem ---- settings --------------------------------------------------------------
set "ONLY=d"
if not "%~1"=="" set "ONLY=%~1"
if /i "%ONLY%"=="all" set "ONLY="
rem Leave MODEL empty to use LANTERN_MODEL from .env (default gemini-robotics-er-2-preview).
rem Example: set "MODEL=gemini-2.5-flash"
set "MODEL="
set "TODAY=2026-10-10"
rem ----------------------------------------------------------------------------

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found on PATH. Install Python 3.10+ and try again.
  goto :end
)

if not exist ".env" (
  echo No .env file found. Copy .env.example to .env and put your GEMINI_API_KEY in it.
  goto :end
)

if not exist "logs" mkdir "logs"

echo.
echo ===== 1/4  Installing requirements =====
python -m pip install -q -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo ===== 2/4  Unit tests (offline) =====
python -m pytest -q
if errorlevel 1 goto :fail

echo.
echo ===== 3/4  Offline demo (simulated camera, real vault rules) =====
python -m lantern.cli demo --today %TODAY%
if errorlevel 1 goto :fail

echo.
echo ===== 4/4  LIVE demo: sending the sample images to Gemini =====
set "ARGS=--mode gemini --today %TODAY%"
if defined ONLY set "ARGS=%ARGS% --only %ONLY%"
if defined MODEL set "ARGS=%ARGS% --model %MODEL%"
echo python -m lantern.cli demo %ARGS%
echo (free tier allows only a few requests per minute; the demo waits when rate limited)
echo.
python -u -m lantern.cli demo %ARGS% 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath 'logs\gemini_live.log'"
echo.
echo Live output saved to logs\gemini_live.log
goto :end

:fail
echo.
echo A step failed. See the messages above.

:end
echo.
if not defined NOPAUSE pause
endlocal
