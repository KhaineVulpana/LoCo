@echo off
REM LoCo Agent Server - Windows Installer Packaging Script
REM Creates a complete installer using Inno Setup

echo ================================
echo LoCo Agent Server - Windows Installer Build
echo ================================
echo.

REM Check if we're in the right directory
if not exist "backend\app\main.py" (
    echo ERROR: Please run this script from the LoCo project root directory
    echo Expected structure: backend\app\main.py
    pause
    exit /b 1
)

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

REM Check for Inno Setup
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo WARNING: Inno Setup not found at default location
    echo Please install Inno Setup from https://jrsoftware.org/isdl.php
    echo Or update the path in this script
    pause
    exit /b 1
)

echo [1/6] Installing PyInstaller...
pip install pyinstaller --quiet

echo [2/6] Installing server dependencies...
cd backend
pip install -r requirements.txt --quiet

echo [3/6] Creating PyInstaller spec file...
pyi-makespec ^
    --name "LoCoAgent" ^
    --onefile ^
    --noconsole ^
    --add-data "app;app" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols" ^
    --hidden-import "uvicorn.protocols.http" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "uvicorn.lifespan" ^
    --hidden-import "uvicorn.lifespan.on" ^
    app\main.py

echo [4/6] Building executable...
pyinstaller LoCoAgent.spec --clean --noconfirm

if not exist "dist\LoCoAgent.exe" (
    echo ERROR: Build failed! Executable not created.
    cd ..
    pause
    exit /b 1
)

cd ..

echo [5/6] Preparing installer files...
if not exist "installer_build" mkdir installer_build
if not exist "installer_build\bin" mkdir installer_build\bin
if not exist "installer_build\config" mkdir installer_build\config
if not exist "installer_build\scripts" mkdir installer_build\scripts

REM Copy executable
copy backend\dist\LoCoAgent.exe installer_build\bin\LoCoAgent.exe

REM Create default config
(
echo PORT=3199
echo DEBUG=false
echo DATABASE_URL=sqlite+aiosqlite:///{app}\data\loco_agent.db
echo QDRANT_HOST=localhost
echo QDRANT_PORT=6333
echo MODEL_PROVIDER=ollama
echo MODEL_NAME=qwen3-coder:30B-a3b-q4_K_M
echo MODEL_URL=http://localhost:11434
echo MAX_CONTEXT_TOKENS=16384
echo MAX_RESPONSE_TOKENS=4096
) > installer_build\config\.env.default

REM Create launcher script
(
echo @echo off
echo cd /d "%%~dp0"
echo echo Starting LoCo Agent Server...
echo.
echo REM Set data directory
echo set LOCO_DATA_DIR=%%APPDATA%%\LoCoAgent
echo if not exist "%%LOCO_DATA_DIR%%" mkdir "%%LOCO_DATA_DIR%%"
echo if not exist "%%LOCO_DATA_DIR%%\data" mkdir "%%LOCO_DATA_DIR%%\data"
echo.
echo REM Copy default config if not exists
echo if not exist "%%LOCO_DATA_DIR%%\.env" ^(
echo     copy "config\.env.default" "%%LOCO_DATA_DIR%%\.env"
echo     echo Created default configuration at %%LOCO_DATA_DIR%%\.env
echo ^)
echo.
echo REM Change to data directory
echo cd /d "%%LOCO_DATA_DIR%%"
echo.
echo REM Start server
echo "%%~dp0bin\LoCoAgent.exe"
) > installer_build\scripts\start-loco.bat

REM Create service installer script
(
echo @echo off
echo REM Install LoCo Agent as Windows Service using NSSM
echo echo Installing LoCo Agent Service...
echo.
echo set INSTALL_DIR=%%~dp0..
echo set DATA_DIR=%%APPDATA%%\LoCoAgent
echo.
echo REM Check for NSSM
echo if not exist "%%INSTALL_DIR%%\bin\nssm.exe" ^(
echo     echo ERROR: NSSM not found. Please download from nssm.cc
echo     pause
echo     exit /b 1
echo ^)
echo.
echo REM Install service
echo "%%INSTALL_DIR%%\bin\nssm.exe" install LoCoAgent "%%INSTALL_DIR%%\bin\LoCoAgent.exe"
echo "%%INSTALL_DIR%%\bin\nssm.exe" set LoCoAgent AppDirectory "%%DATA_DIR%%"
echo "%%INSTALL_DIR%%\bin\nssm.exe" set LoCoAgent DisplayName "LoCo Agent Server"
echo "%%INSTALL_DIR%%\bin\nssm.exe" set LoCoAgent Description "Local-first coding agent server"
echo "%%INSTALL_DIR%%\bin\nssm.exe" set LoCoAgent Start SERVICE_AUTO_START
echo.
echo echo Service installed successfully!
echo echo Run 'net start LoCoAgent' to start the service
echo pause
) > installer_build\scripts\install-service.bat

REM Create uninstall service script
(
echo @echo off
echo echo Uninstalling LoCo Agent Service...
echo.
echo set INSTALL_DIR=%%~dp0..
echo.
echo "%%INSTALL_DIR%%\bin\nssm.exe" stop LoCoAgent
echo "%%INSTALL_DIR%%\bin\nssm.exe" remove LoCoAgent confirm
echo.
echo echo Service uninstalled successfully!
echo pause
) > installer_build\scripts\uninstall-service.bat

REM Create Inno Setup script
(
echo ; LoCo Agent Server Installer Script
echo #define MyAppName "LoCo Agent Server"
echo #define MyAppVersion "1.0.0"
echo #define MyAppPublisher "LoCo Project"
echo #define MyAppURL "https://github.com/yourrepo/loco"
echo #define MyAppExeName "LoCoAgent.exe"
echo.
echo [Setup]
echo AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
echo AppName={#MyAppName}
echo AppVersion={#MyAppVersion}
echo AppPublisher={#MyAppPublisher}
echo AppPublisherURL={#MyAppURL}
echo AppSupportURL={#MyAppURL}
echo AppUpdatesURL={#MyAppURL}
echo DefaultDirName={autopf}\{#MyAppName}
echo DefaultGroupName={#MyAppName}
echo AllowNoIcons=yes
echo LicenseFile=..\LICENSE
echo OutputDir=..\releases
echo OutputBaseFilename=LoCoAgent-Server-Setup
echo Compression=lzma
echo SolidCompression=yes
echo WizardStyle=modern
echo PrivilegesRequired=admin
echo.
echo [Languages]
echo Name: "english"; MessagesFile: "compiler:Default.isl"
echo.
echo [Tasks]
echo Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
echo Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
echo Name: "autostart"; Description: "Start LoCo Agent automatically with Windows"; GroupDescription: "Startup Options:"; Flags: unchecked
echo.
echo [Files]
echo Source: "installer_build\bin\{#MyAppExeName}"; DestDir: "{app}\bin"; Flags: ignoreversion
echo Source: "installer_build\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
echo Source: "installer_build\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion
echo.
echo [Dirs]
echo Name: "{commonappdata}\LoCoAgent"; Permissions: users-full
echo Name: "{commonappdata}\LoCoAgent\data"; Permissions: users-full
echo Name: "{commonappdata}\LoCoAgent\logs"; Permissions: users-full
echo.
echo [Icons]
echo Name: "{group}\{#MyAppName}"; Filename: "{app}\scripts\start-loco.bat"; IconFilename: "{app}\bin\{#MyAppExeName}"
echo Name: "{group}\Configure LoCo Agent"; Filename: "notepad.exe"; Parameters: "{commonappdata}\LoCoAgent\.env"
echo Name: "{group}\View Logs"; Filename: "{commonappdata}\LoCoAgent\logs"
echo Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
echo Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\scripts\start-loco.bat"; IconFilename: "{app}\bin\{#MyAppExeName}"; Tasks: desktopicon
echo.
echo [Run]
echo Filename: "{app}\scripts\start-loco.bat"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent shellexec
echo.
echo [Code]
echo procedure InitializeWizard;
echo begin
echo   WizardForm.LicenseAcceptedRadio.Checked := True;
echo end;
echo.
echo function InitializeSetup(): Boolean;
echo begin
echo   Result := True;
echo   if not IsDotNetInstalled(net472, 0^) then
echo   begin
echo     MsgBox('LoCo Agent requires .NET Framework 4.7.2 or later.' #13#13 
echo            'Please install it from https://dotnet.microsoft.com/', mbError, MB_OK^);
echo     Result := False;
echo   end;
echo end;
echo.
echo procedure CurStepChanged(CurStep: TSetupStep^);
echo var
echo   ResultCode: Integer;
echo   DataDir: String;
echo begin
echo   if CurStep = ssPostInstall then
echo   begin
echo     DataDir := ExpandConstant('{commonappdata}\LoCoAgent'^);
echo     
echo     // Copy default config if not exists
echo     if not FileExists(DataDir + '\.env'^) then
echo     begin
echo       FileCopy(ExpandConstant('{app}\config\.env.default'^), DataDir + '\.env', False^);
echo     end;
echo     
echo     // Create initial database directory
echo     ForceDirectories(DataDir + '\data'^);
echo     ForceDirectories(DataDir + '\logs'^);
echo   end;
echo end;
) > installer_build\loco-installer.iss

echo [6/6] Building installer with Inno Setup...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_build\loco-installer.iss

if not exist "releases\LoCoAgent-Server-Setup.exe" (
    echo ERROR: Installer build failed!
    pause
    exit /b 1
)

echo.
echo ================================
echo Build Complete!
echo ================================
echo.
echo Installer: releases\LoCoAgent-Server-Setup.exe
echo.
echo The installer will:
echo - Install LoCo Agent to Program Files
echo - Create data directory in AppData\LoCoAgent
echo - Set up default configuration
echo - Create Start Menu shortcuts
echo - Optionally create desktop shortcut
echo - Optionally set up Windows service
echo.
echo Distribution ready for release!
echo.
pause
