@echo off
REM LoCo Agent Startup Script for Windows
REM Starts Qdrant and Server together

echo Starting LoCo Agent...
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Start Qdrant
echo Starting Qdrant vector database...
docker compose up -d qdrant

REM Wait for Qdrant to be healthy
echo Waiting for Qdrant to be ready...
timeout /t 5 /nobreak >nul

:check_qdrant
curl -f http://localhost:6333/ >nul 2>&1
if errorlevel 1 (
    echo Qdrant not ready yet, waiting...
    timeout /t 2 /nobreak >nul
    goto check_qdrant
)

echo Qdrant is healthy
echo.

REM Start server
echo Starting server...
cd server

REM Find Python executable (skip Windows Store stub)
set PYTHON_EXE=
for %%p in (
    "C:\Users\Kevin\AppData\Local\Programs\Python\Python311\python.exe"
    "C:\Users\Kevin\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python312\python.exe"
) do (
    if exist %%p (
        set PYTHON_EXE=%%p
        goto :found_python
    )
)

echo Error: Python 3.11 or 3.12 not found. Please install Python.
pause
exit /b 1

:found_python
echo Found Python: %PYTHON_EXE%

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    %PYTHON_EXE% -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate venv
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Warning: Some dependencies may have conflicts, but continuing...
)

REM Start server
echo.
echo Server starting on http://localhost:3199
echo.
echo    Health: http://localhost:3199/v1/health
echo    Qdrant: http://localhost:6333
echo.
echo Press Ctrl+C to stop
echo.

uvicorn app.main:app --reload --port 3199
