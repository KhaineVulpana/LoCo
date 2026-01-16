@echo off
setlocal EnableExtensions EnableDelayedExpansion
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
    if exist "%USERPROFILE%\.cargo\bin\cargo.exe" (
        set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    )
    cargo --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Rust/Cargo is not installed
        echo Please install Rust from https://www.rust-lang.org/tools/install
        pause
        exit /b 1
    )
)

REM Ensure a compatible Rust toolchain is available for building the Tauri CLI
set "TAURI_CLI_TOOLCHAIN=1.79.0"
rustup --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: rustup is required to install the Tauri toolchain
    echo Please install Rust from https://www.rust-lang.org/tools/install
    pause
    exit /b 1
)
rustup toolchain list | findstr /C:"%TAURI_CLI_TOOLCHAIN%" >nul
if errorlevel 1 (
    echo Installing Rust toolchain %TAURI_CLI_TOOLCHAIN%...
    rustup toolchain install %TAURI_CLI_TOOLCHAIN%
    if errorlevel 1 (
        echo ERROR: Failed to install Rust toolchain %TAURI_CLI_TOOLCHAIN%
        pause
        exit /b 1
    )
)

REM Check for Tauri CLI (v1.x required for this module)
set "TAURI_VERSION="
set "TAURI_MAJOR="
set "USE_LOCAL_TAURI=0"
for /f "tokens=2" %%V in ('cargo tauri --version 2^>nul') do set "TAURI_VERSION=%%V"
if defined TAURI_VERSION (
    for /f "tokens=1 delims=." %%M in ("%TAURI_VERSION%") do set "TAURI_MAJOR=%%M"
)
if not defined TAURI_VERSION (
    set "USE_LOCAL_TAURI=1"
)
if defined TAURI_MAJOR if not "%TAURI_MAJOR%"=="1" (
    set "USE_LOCAL_TAURI=1"
)
if "%USE_LOCAL_TAURI%"=="1" (
    set "LOCAL_TAURI_ROOT=%CD%\packaging\.tauri-cli"
    set "LOCAL_TAURI_BIN=!LOCAL_TAURI_ROOT!\bin\cargo-tauri.exe"
    if not exist "!LOCAL_TAURI_BIN!" (
        echo Installing tauri-cli 1.5.0...
        cargo +%TAURI_CLI_TOOLCHAIN% install tauri-cli --version 1.5.0 --locked --root "!LOCAL_TAURI_ROOT!"
        if errorlevel 1 (
            echo ERROR: Failed to install tauri-cli
            pause
            exit /b 1
        )
    )
    set "PATH=!LOCAL_TAURI_ROOT!\bin;%PATH%"
)

echo [1/2] Building Tauri bundles...
cd modules\3d-gen-desktop\src-tauri
cargo tauri build
if errorlevel 1 (
    echo ERROR: Tauri build failed
    cd ..\..\..
    pause
    exit /b 1
)
cd ..\..\..

echo [2/2] Collecting artifacts...
if not exist "out" mkdir out

set BUNDLE_DIR=modules\3d-gen-desktop\src-tauri\target\release\bundle
set FOUND=0

for %%F in ("%BUNDLE_DIR%\msi\*.msi") do (
    if exist "%%~fF" (
        copy "%%~fF" "out\" >nul
        set FOUND=1
    )
)

for %%F in ("%BUNDLE_DIR%\nsis\*.exe") do (
    if exist "%%~fF" (
        copy "%%~fF" "out\" >nul
        set FOUND=1
    )
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
