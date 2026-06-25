@echo off
setlocal
cd /d "%~dp0"

set "API_PORT=8000"
set "WEB_PORT=5180"
set "WEB_URL=http://localhost:%WEB_PORT%"
set "PY=.venv\Scripts\python.exe"

echo ============================================================
echo   Crypto Analyst - launcher
echo   API  : http://localhost:%API_PORT%
echo   App  : %WEB_URL%
echo ============================================================
echo.

REM --- sanity checks --------------------------------------------------------
if not exist "%~dp0%PY%" (
  echo [ERROR] Python venv not found at "%~dp0%PY%".
  echo Create it first:
  echo     uv venv --python 3.11 .venv
  echo     uv pip install --python .venv\Scripts\python.exe -e .
  echo.
  pause
  exit /b 1
)

if not exist "%~dp0frontend\node_modules" (
  echo [setup] Installing frontend dependencies ^(first run only^)...
  pushd "%~dp0frontend"
  call npm install --no-fund --no-audit
  popd
  echo.
)

REM --- refresh data (best-effort; harmless if offline) ----------------------
echo [data] Refreshing BTC/ETH 1h candles ^(best-effort^)...
"%PY%" -m analyst.ingest --symbols BTC_USDT,ETH_USDT --timeframe 1h --count 300
echo [data] Capturing a microstructure snapshot ^(best-effort^)...
"%PY%" -m analyst.collect_micro --symbols BTC_USDT,ETH_USDT
echo.

REM --- start the API in its own window --------------------------------------
echo [api] Starting analyst API on port %API_PORT% ...
start "Analyst API" /D "%~dp0" cmd /k %PY% -m uvicorn analyst.api.app:app --port %API_PORT%

REM --- start the visualizer in its own window -------------------------------
echo [web] Starting visualizer on port %WEB_PORT% ...
start "Analyst Frontend" /D "%~dp0frontend" cmd /k npm run dev

REM --- wait for the dev server, then open the browser -----------------------
echo [wait] Letting servers boot...
timeout /t 6 /nobreak >nul
echo [open] Opening %WEB_URL%
start "" "%WEB_URL%"

echo.
echo ------------------------------------------------------------
echo Two terminal windows are now running (API + visualizer).
echo Close those windows to stop the servers.
echo ------------------------------------------------------------
endlocal
