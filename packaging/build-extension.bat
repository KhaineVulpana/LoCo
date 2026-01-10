@echo off
REM LoCo Agent VS Code Extension - Packaging Script (Windows)
REM Creates .vsix file for distribution

echo ================================
echo LoCo VS Code Extension - Build
echo ================================

REM Check if we're in the right directory
if not exist "modules\vscode-extension\package.json" (
    echo ERROR: Please run this script from the LoCo project root directory
    echo Expected structure: modules\vscode-extension\package.json
    pause
    exit /b 1
)

REM Check for Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

REM Check for npm
npm --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm is not installed
    pause
    exit /b 1
)

echo [1/5] Installing dependencies...
cd modules/vscode-extension
call npm install

echo [2/5] Installing vsce (VS Code Extension Manager)...
call npm install -g @vscode/vsce --quiet

echo [3/5] Running tests...
call npm test || echo Warning: Tests failed or not configured

echo [4/5] Building extension...
call npm run compile

if not exist "out\" (
    echo ERROR: Build failed! 'out' directory not created.
    cd ..\..
    pause
    exit /b 1
)

echo [5/5] Packaging extension...

REM Create out directory
cd ..\..
if not exist "out" mkdir out

REM Get version from package.json
cd modules/vscode-extension
for /f "tokens=2 delims=:, " %%i in ('findstr /r "\"version\"" package.json') do set VERSION=%%i
set VERSION=%VERSION:"=%
echo Extension version: %VERSION%

REM Package the extension
call vsce package --out ..\..\out\

cd ..\..

set VSIX_FILE=out\loco-agent-%VERSION%.vsix

if not exist "%VSIX_FILE%" (
    echo ERROR: Packaging failed! .vsix file not created.
    pause
    exit /b 1
)

echo.
echo ================================
echo Build Complete!
echo ================================
echo.
echo Extension package: %VSIX_FILE%
echo.
echo To install:
echo   1. Open VS Code
echo   2. Go to Extensions (Ctrl+Shift+X^)
echo   3. Click '...' menu -^> 'Install from VSIX...'
echo   4. Select: %VSIX_FILE%
echo.
echo Or install via command line:
echo   code --install-extension %VSIX_FILE%
echo.
echo To publish to marketplace:
echo   vsce publish
echo   (Requires: https://marketplace.visualstudio.com publisher account^)
echo.
pause
