@echo off
REM LoCo Agent Frontend Suite Startup Script (Windows)

setlocal
set MODE=%1
if "%MODE%"=="" set MODE=web

set MODULE_DIR=modules\agent-ui

where node >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js not found. Please install Node.js 18+.
    exit /b 1
)

if not exist "%MODULE_DIR%" (
    echo Error: %MODULE_DIR% not found.
    exit /b 1
)

cd %MODULE_DIR%

if not exist "node_modules" (
    echo Installing frontend dependencies...
    npm install
    if errorlevel 1 (
        echo Error: npm install failed.
        exit /b 1
    )
)

if "%MODE%"=="desktop" (
    where cargo >nul 2>&1
    if errorlevel 1 (
        echo Error: Rust toolchain not found. Install Rust ^(https://www.rust-lang.org/tools/install^).
        exit /b 1
    )
    echo Starting desktop app ^(Tauri^)...
    cd src-tauri
    cargo tauri dev
    exit /b %errorlevel%
)

echo Starting frontend dev server...
echo Open http://localhost:5173/app/

npm run dev -- --host
