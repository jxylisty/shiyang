@echo off
setlocal enabledelayedexpansion
title Shiyang - Start All Services

REM Resolve project root (strip trailing backslash)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

echo ============================================
echo   Shiyang (Herb Tea Analysis) - One Click Start
echo ============================================
echo.

REM ---------- 1. Environment check ----------
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found. Install Python 3.10+ and add to PATH.
    pause & exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] node not found. Install Node.js 20+.
    pause & exit /b 1
)

if not exist "%ROOT%\data\shiyang.db" (
    echo [ERROR] data\shiyang.db missing - knowledge base is not tracked in git.
    echo         Restore it from backup or rebuild per docs.
    pause & exit /b 1
)

python -c "import rapidocr_onnxruntime" >nul 2>&1
if errorlevel 1 (
    echo [WARN] rapidocr-onnxruntime missing - image OCR will fall back to online
    echo        Fix: pip install -r "%ROOT%\backend\requirements.txt"
    echo.
)

REM ---------- 2. Detect LAN IP ----------
REM ipconfig lists virtual adapters first (Tailscale 100.x, WSL 172.x.240.1),
REM so ask the OS which source address it would use to reach the internet.
set "LANIP="
for /f "delims=" %%a in ('python -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));print(s.getsockname()[0]);s.close()" 2^>nul') do set "LANIP=%%a"
if not defined LANIP set "LANIP=127.0.0.1"

REM ---------- 3. Backend :8100 ----------
echo [1/2] Starting backend on :8100 ...
netstat -ano | findstr ":8100" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "Shiyang-Backend-8100" cmd /k "cd /d "%ROOT%\backend" && python -X utf8 -m uvicorn app.main:app --port 8100"
) else (
    echo       Port 8100 already listening - skipped
)

set /a WAITED=0
:WAIT_BACKEND
timeout /t 2 /nobreak >nul 2>&1
set /a WAITED+=2
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/api/v1/health' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto BACKEND_OK
if !WAITED! lss 20 goto WAIT_BACKEND
echo       [WARN] backend not ready within 20s - check the backend window
goto START_FRONT
:BACKEND_OK
echo       Backend ready

REM ---------- 4. Frontend :5174 ----------
:START_FRONT
echo [2/2] Starting frontend on :5174 ...
netstat -ano | findstr ":5174" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "Shiyang-Frontend-5174" cmd /k "cd /d "%ROOT%\frontend" && npx vite --port 5174"
) else (
    echo       Port 5174 already listening - skipped
)

set /a WAITED=0
:WAIT_FRONT
timeout /t 2 /nobreak >nul 2>&1
set /a WAITED+=2
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5174/' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto FRONT_OK
if !WAITED! lss 25 goto WAIT_FRONT
echo       [WARN] frontend not ready within 25s - check the frontend window
goto SHOW
:FRONT_OK
echo       Frontend ready

REM ---------- 5. URLs ----------
:SHOW
echo.
echo ============================================
echo   Ready
echo ============================================
echo   Local    : http://127.0.0.1:5174
echo   LAN      : http://%LANIP%:5174
echo              (same WiFi - phone or teammate)
echo.
echo   API docs : http://127.0.0.1:8100/docs
echo   Stop     : close the two service windows
echo ============================================
echo.

start "" "http://127.0.0.1:5174"

echo Press any key to close this window (services keep running)
pause >nul
endlocal
