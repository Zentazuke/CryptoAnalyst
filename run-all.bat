@echo off
setlocal
cd /d "%~dp0"

REM ---- paths & ports -------------------------------------------------------
REM (2026-07-04: sentiment engine retired — the analyst runs standalone and all
REM  sentiment consumers fail open. The sentiment LAYER returns only when a
REM  calibrated source earns it via the P1.2 harness.)
set "ANALYST=%~dp0"
set "APY=.venv\Scripts\python.exe"
set "API_PORT=8000"
set "WEB_PORT=5180"
set "WEB_URL=http://localhost:%WEB_PORT%"

echo ============================================================
echo   Crypto Analyst
echo   Analyst API   : http://localhost:%API_PORT%
echo   Dashboard     : %WEB_URL%
echo ============================================================
echo.

REM ---- sanity checks -------------------------------------------------------
if not exist "%ANALYST%%APY%" (
  echo [ERROR] analyst venv missing at "%ANALYST%%APY%". See README setup. & pause & exit /b 1
)
if not exist "%ANALYST%frontend\node_modules" (
  echo [setup] Installing frontend deps ^(first run only^)...
  pushd "%ANALYST%frontend" & call npm install --no-fund --no-audit & popd
)

REM ---- free ports from any previous run ------------------------------------
echo [ports] Releasing %API_PORT% / %WEB_PORT% if in use...
powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort %API_PORT%,%WEB_PORT% -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
echo.

REM ---- analyst data (writers run before the read-only API) -----------------
echo [data] Refreshing BTC/ETH candles + microstructure ^(best-effort^)...
"%APY%" -m analyst.ingest --symbols BTC_USDT,ETH_USDT --timeframe 1h --count 1000
"%APY%" -m analyst.collect_micro --symbols BTC_USDT,ETH_USDT
echo.

REM ---- analyst API + dashboard ---------------------------------------------
echo [analyst] Starting analyst API + visualizer (with background scheduler)...
start "Analyst API" /D "%ANALYST%" cmd /k set ANALYST_SCHEDULER=1 ^& %APY% -m uvicorn analyst.api.app:app --host 127.0.0.1 --port %API_PORT%
start "Analyst Frontend" /D "%ANALYST%frontend" cmd /k npm run dev

REM ---- wait for the analyst API to be ready, then open the dashboard -------
echo [wait] Waiting for the analyst API to be ready...
powershell -NoProfile -Command "$u='http://127.0.0.1:%API_PORT%/health'; for($i=0;$i -lt 60;$i++){ try{ if((Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200){ Write-Host '  API ready.'; exit 0 } }catch{}; Start-Sleep -Milliseconds 700 }"
echo [open] Opening %WEB_URL%
start "" "%WEB_URL%"

echo.
echo ------------------------------------------------------------
echo Running windows: Analyst API, Analyst Frontend
echo Close the terminal windows to stop everything.
echo ------------------------------------------------------------
endlocal
