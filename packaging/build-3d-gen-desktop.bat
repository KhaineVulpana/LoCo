@echo off
REM LoCo 3D-Gen Desktop - Tauri Packaging Script (Windows)
REM Creates installer bundles for distribution

echo ================================
echo LoCo 3D-Gen Desktop - Build
echo ================================
echo.

REM Check if we're in the right directory
if not exist "modules\3d-gen-desktop\src-tauri\Cargo.toml" (
    echo ERROR: Please run this script from the LoCo project root directory
    echo Expected structure: modules\3d-gen-desktop\src-tauri\Cargo.toml
    pause
    exit /b 1
)

REM Check for Cargo
cargo --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Rust/Cargo is not installed
    echo Please install Rust from https://www.rust-lang.org/tools/install
    pause
    exit /b 1
)

REM Check for Tauri CLI
cargo tauri --version >nul 2>&1
if errorlevel 1 (
    echo Installing tauri-cli...
    cargo install tauri-cli --version 1.5.0
    if errorlevel 1 (
        echo ERROR: Failed to install tauri-cli
        pause
        exit /b 1
    )
)

echo [1/2] Building Tauri bundles...
cd modules\3d-gen-desktop\src-tauri
cargo tauri build
if errorlevel 1 (
    echo ERROR: Tauri build failed
    cd ..\..
    pause
    exit /b 1
)
cd ..\..

echo [2/2] Collecting artifacts...
if not exist "out" mkdir out

set BUNDLE_DIR=modules\3d-gen-desktop\src-tauri\target\release\bundle
set FOUND=0

for /f %%F in ('dir /b "%BUNDLE_DIR%\msi\*.msi" 2^>nul') do (
    copy "%BUNDLE_DIR%\msi\%%F" "out\" >nul
    set FOUND=1
)

for /f %%F in ('dir /b "%BUNDLE_DIR%\nsis\*.exe" 2^>nul') do (
    copy "%BUNDLE_DIR%\nsis\%%F" "out\" >nul
    set FOUND=1
)

if "%FOUND%"=="0" (
    echo ERROR: No bundled artifacts found in %BUNDLE_DIR%
    pause
    exit /b 1
)

echo.
echo ================================
echo Build Complete!
echo ================================
echo.
echo Output folder: out
echo.
pause
