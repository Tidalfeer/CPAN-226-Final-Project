@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo    Autonomous Network Resilience Agent - Windows Demo
echo ============================================================
echo.

REM Check Python
echo  Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python not found!
    pause
    exit /b 1
)
echo  Python found
echo.

REM Install dependencies
echo  Installing dependencies...
pip install -r requirements.txt -q
echo  Dependencies ready
echo.

REM Check Ollama
echo  Checking Ollama...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo  WARNING: Ollama not running
    echo  Please start Ollama first
    pause
    exit /b 1
)
echo  Ollama running
echo.

REM Create directories
if not exist "logs" mkdir logs
echo  Directories ready
echo.

REM Start FastAPI Server
echo  Starting FastAPI Mock Server...
start /B python run_mock_server.py
timeout /t 3 /nobreak >nul

REM Test server
curl -s http://127.0.0.1:5001/health >nul 2>&1
if errorlevel 1 (
    echo  WARNING: Server may not have started
) else (
    echo  Server running at http://127.0.0.1:5001
)
echo.

REM Open Dashboard
echo  Opening dashboard...
start http://127.0.0.1:5001
echo.

REM Set environment and run agent
echo ============================================================
echo DEMO READY!
echo ============================================================
echo Dashboard: http://127.0.0.1:5001
echo API Docs: http://127.0.0.1:5001/docs
echo.
echo Starting agent in 3 seconds...
echo Press Ctrl+C to stop
echo.

timeout /t 3 /nobreak >nul

set USE_MOCK_SERVER=true
set MOCK_SERVER_URL=http://127.0.0.1:5001
python agent/main.py --interval 5

echo.
echo Demo stopped.
pause