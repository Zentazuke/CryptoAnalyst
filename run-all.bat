@echo off
setlocal
cd /d "%~dp0"

REM ---- paths & ports -------------------------------------------------------
set "ANALYST=%~dp0"
set "SENTIMENT=C:\Users\Ricardo\Desktop\Work\PROJECTOS\sentiment_engine_independent_v1"
set "APY=.venv\Scripts\python.exe"
set "SPY=.venv\Scripts\python.exe"
set "API_PORT=8000"
set "WEB_PORT=5180"
set "SENT_PORT=8787"
set "WEB_URL=http://localhost:%WEB_PORT%"
set "SYMS=BTC/USDT ETH/USDT"

echo ============================================================
echo   Crypto Analyst - FULL STACK (math + sentiment)
echo   Analyst API   : http://localhost:%API_PORT%
echo   Sentiment API : http://localhost:%SENT_PORT%
echo   Dashboard     : %WEB_URL%
echo ============================================================
echo.

REM ---- sanity checks -------------------------------------------------------
if not exist "%ANALYST%%APY%" (
  echo [ERROR] analyst venv missing at "%ANALYST%%APY%". See README setup. & pause & exit /b 1
)
set "HAVE_SENT=1"
if not exist "%SENTIMENT%\%SPY%" (
  echo [WARN] sentiment engine venv not found at "%SENTIMENT%\%SPY%".
  echo        Skipping sentiment - the analyst will run without it.
  set "HAVE_SENT=0"
)
if not exist "%ANALYST%frontend\node_modules" (
  echo [setup] Installing frontend deps ^(first run only^)...
  pushd "%ANALYST%frontend" & call npm install --no-fund --no-audit & popd
)

REM ---- free ports from any previous run ------------------------------------
echo [ports] Releasing %API_PORT% / %WEB_PORT% / %SENT_PORT% if in use...
powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort %API_PORT%,%WEB_PORT%,%SENT_PORT% -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
echo.

REM ---- sentiment engine (its own venv) -------------------------------------
if "%HAVE_SENT%"=="1" (
  echo [sentiment] Starting engine API + live feeds...
  start "Sentiment API" /D "%SENTIMENT%" cmd /k %SPY% -m uvicorn sentiment_engine.api:app --host 127.0.0.1 --port %SENT_PORT%
  start "Sentiment Feeds" /D "%SENTIMENT%" cmd /k %SPY% -m sentiment_engine.ingestion.run_live --sources binance news bluesky context lsr deriv --symbols %SYMS%
)
echo.

REM ---- analyst data (writers run before the read-only API) -----------------
echo [data] Refreshing BTC/ETH candles + microstructure ^(best-effort^)...
"%APY%" -m analyst.ingest --symbols BTC_USDT,ETH_USDT --timeframe 1h --count 1000
"%APY%" -m analyst.collect_micro --symbols BTC_USDT,ETH_USDT
echo.

REM ---- analyst API + dashboard ---------------------------------------------
echo [analyst] Starting analyst API + visualizer...
start "Analyst API" /D "%ANALYST%" cmd /k %APY% -m uvicorn analyst.api.app:app --host 127.0.0.1 --port %API_PORT%
start "Analyst Frontend" /D "%ANALYST%frontend" cmd /k npm run dev

REM ---- open the dashboard --------------------------------------------------
echo [wait] Letting servers boot...
timeout /t 7 /nobreak >nul
echo [open] Opening %WEB_URL%
start "" "%WEB_URL%"

echo.
echo ------------------------------------------------------------
echo Running windows: Analyst API, Analyst Frontend%HAVE_SENT:1=, Sentiment API, Sentiment Feeds%
echo Sentiment feeds need ~1-2 min to warm up before the Sentiment card fills.
echo Close the terminal windows to stop everything.
echo ------------------------------------------------------------
endlocal
