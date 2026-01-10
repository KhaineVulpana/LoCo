@echo off
REM LoCo Agent Android App - APK Build Script (Windows)
REM Creates signed APK for distribution

echo ================================
echo LoCo Android App - Build APK
echo ================================
echo.

REM Check if we're in the Android project directory
if not exist "app\build.gradle.kts" (
    echo ERROR: Please run this script from the Android project root directory
    echo Expected structure: app\build.gradle.kts
    pause
    exit /b 1
)

REM Check for Java
java -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Java is not installed
    echo Please install Java 17 from https://adoptium.net/
    pause
    exit /b 1
)

REM Detect build type
set BUILD_TYPE=debug
set SIGN_APK=false

echo Build Options:
echo 1. Debug APK (unsigned, for testing)
echo 2. Release APK (requires keystore for signing)
echo.
set /p choice="Select build type [1-2]: "

if "%choice%"=="1" (
    set BUILD_TYPE=debug
    set SIGN_APK=false
) else if "%choice%"=="2" (
    set BUILD_TYPE=release
    set SIGN_APK=true
) else (
    echo Invalid choice. Building debug APK...
    set BUILD_TYPE=debug
    set SIGN_APK=false
)

echo.
echo Building %BUILD_TYPE% APK...
echo.

if "%SIGN_APK%"=="true" (
    echo [1/5] Checking for keystore...
    
    set KEYSTORE_FILE=keystore\loco-release.keystore
    set KEYSTORE_PROPERTIES=keystore.properties
    
    if not exist "%KEYSTORE_FILE%" (
        echo No keystore found. Creating new keystore...
        if not exist "keystore" mkdir keystore
        
        set /p KEYSTORE_PASSWORD="Enter keystore password: "
        set /p KEY_ALIAS="Enter key alias: "
        set /p KEY_PASSWORD="Enter key password: "
        
        keytool -genkeypair -v ^
            -keystore "%KEYSTORE_FILE%" ^
            -alias "%KEY_ALIAS%" ^
            -keyalg RSA ^
            -keysize 2048 ^
            -validity 10000 ^
            -storepass "%KEYSTORE_PASSWORD%" ^
            -keypass "%KEY_PASSWORD%"
        
        REM Create keystore.properties
        (
            echo storePassword=%KEYSTORE_PASSWORD%
            echo keyPassword=%KEY_PASSWORD%
            echo keyAlias=%KEY_ALIAS%
            echo storeFile=../keystore/loco-release.keystore
        ) > "%KEYSTORE_PROPERTIES%"
        
        echo Keystore created at %KEYSTORE_FILE%
        echo IMPORTANT: Keep this file and password secure!
    ) else (
        if not exist "%KEYSTORE_PROPERTIES%" (
            echo ERROR: Keystore found but keystore.properties is missing
            echo Please create keystore.properties with:
            echo   storePassword=^<password^>
            echo   keyPassword=^<password^>
            echo   keyAlias=^<alias^>
            echo   storeFile=../keystore/loco-release.keystore
            pause
            exit /b 1
        )
        echo Using existing keystore: %KEYSTORE_FILE%
    )
    
    echo [2/5] Cleaning previous builds...
    call gradlew.bat clean
    
    echo [3/5] Running lint checks...
    call gradlew.bat lintRelease || echo Warning: Lint issues found
    
    echo [4/5] Building signed release APK...
    call gradlew.bat assembleRelease
    
    set APK_PATH=app\build\outputs\apk\release\app-release.apk
    
) else (
    echo [1/3] Cleaning previous builds...
    call gradlew.bat clean
    
    echo [2/3] Building debug APK...
    call gradlew.bat assembleDebug
    
    set APK_PATH=app\build\outputs\apk\debug\app-debug.apk
)

if not exist "%APK_PATH%" (
    echo ERROR: Build failed! APK not created.
    pause
    exit /b 1
)

echo [Final] Preparing distribution...

REM Create out directory
for %%I in ("%CD%\..\..") do set ROOT_DIR=%%~fI
set OUTPUT_DIR=%ROOT_DIR%\out
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Get version from build.gradle.kts
for /f "tokens=2 delims==\" " %%i in ('findstr /r "versionName" app\build.gradle.kts') do set VERSION=%%i

if "%BUILD_TYPE%"=="release" (
    set OUTPUT_FILE=%OUTPUT_DIR%\LoCoAgent-%VERSION%-release.apk
    
    REM Copy the signed APK
    copy "%APK_PATH%" "%OUTPUT_FILE%"
    
    REM Verify signature
    echo Verifying signature...
    jarsigner -verify -verbose -certs "%OUTPUT_FILE%" || echo Warning: Signature verification had issues
    
) else (
    set OUTPUT_FILE=%OUTPUT_DIR%\LoCoAgent-%VERSION%-debug.apk
    copy "%APK_PATH%" "%OUTPUT_FILE%"
)

echo.
echo ================================
echo Build Complete!
echo ================================
echo.
echo APK: %OUTPUT_FILE%
echo Version: %VERSION%
echo Build Type: %BUILD_TYPE%
echo.

if "%BUILD_TYPE%"=="release" (
    echo This is a SIGNED RELEASE APK ready for distribution.
    echo.
    echo To install on device:
    echo   adb install -r %OUTPUT_FILE%
    echo.
    echo Or transfer to device and install manually.
    echo.
    echo IMPORTANT: Keep your keystore safe! You'll need it for updates.
) else (
    echo This is a DEBUG APK for testing only.
    echo.
    echo To install on device:
    echo   adb install -r %OUTPUT_FILE%
    echo.
    echo For production release, run this script and select option 2.
)

echo.
echo APK Location: %OUTPUT_FILE%
echo.
pause
