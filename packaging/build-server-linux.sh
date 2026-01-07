#!/bin/bash
# LoCo Agent Server - Linux/macOS Packaging Script
# Creates standalone executable and installer using PyInstaller

set -e

echo "================================"
echo "LoCo Agent Server - Build"
echo "================================"
echo

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    INSTALLER_EXT="run"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    INSTALLER_EXT="pkg"
else
    echo "ERROR: Unsupported OS: $OSTYPE"
    exit 1
fi

echo "Building for: $OS"
echo

# Check if we're in the right directory
if [ ! -f "backend/app/main.py" ]; then
    echo "ERROR: Please run this script from the LoCo project root directory"
    echo "Expected structure: backend/app/main.py"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.10+ from https://www.python.org/"
    exit 1
fi

echo "[1/6] Installing PyInstaller..."
pip3 install pyinstaller --quiet

echo "[2/6] Installing server dependencies..."
cd backend
pip3 install -r requirements.txt --quiet

echo "[3/6] Creating PyInstaller spec file..."
pyi-makespec \
    --name "loco-agent" \
    --onefile \
    --add-data "app:app" \
    --hidden-import "uvicorn.logging" \
    --hidden-import "uvicorn.loops" \
    --hidden-import "uvicorn.loops.auto" \
    --hidden-import "uvicorn.protocols" \
    --hidden-import "uvicorn.protocols.http" \
    --hidden-import "uvicorn.protocols.http.auto" \
    --hidden-import "uvicorn.protocols.websockets" \
    --hidden-import "uvicorn.protocols.websockets.auto" \
    --hidden-import "uvicorn.lifespan" \
    --hidden-import "uvicorn.lifespan.on" \
    app/main.py

echo "[4/6] Building executable..."
pyinstaller loco-agent.spec --clean --noconfirm

if [ ! -f "dist/loco-agent" ]; then
    echo "ERROR: Build failed! Executable not created."
    cd ..
    exit 1
fi

cd ..

echo "[5/6] Preparing installer files..."
mkdir -p installer_build/{bin,config,scripts,systemd}

# Copy executable
cp backend/dist/loco-agent installer_build/bin/
chmod +x installer_build/bin/loco-agent

# Create default config
cat > installer_build/config/.env.default << 'EOF'
PORT=3199
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///{data_dir}/loco_agent.db
QDRANT_HOST=localhost
QDRANT_PORT=6333
MODEL_PROVIDER=ollama
MODEL_NAME=qwen2.5-coder:7b
MODEL_URL=http://localhost:11434
MAX_CONTEXT_TOKENS=16384
MAX_RESPONSE_TOKENS=4096
EOF

# Create launcher script
cat > installer_build/scripts/start-loco.sh << 'EOF'
#!/bin/bash
# LoCo Agent Launcher

# Set data directory
LOCO_DATA_DIR="${HOME}/.local/share/loco-agent"
LOCO_CONFIG_DIR="${HOME}/.config/loco-agent"

# Create directories
mkdir -p "${LOCO_DATA_DIR}/data"
mkdir -p "${LOCO_CONFIG_DIR}"

# Copy default config if not exists
if [ ! -f "${LOCO_CONFIG_DIR}/.env" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cp "${SCRIPT_DIR}/../config/.env.default" "${LOCO_CONFIG_DIR}/.env"
    # Replace {data_dir} with actual path
    sed -i "s|{data_dir}|${LOCO_DATA_DIR}|g" "${LOCO_CONFIG_DIR}/.env"
    echo "Created default configuration at ${LOCO_CONFIG_DIR}/.env"
fi

# Change to config directory
cd "${LOCO_CONFIG_DIR}"

# Start server
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/../bin/loco-agent"
EOF
chmod +x installer_build/scripts/start-loco.sh

# Create systemd service file (Linux only)
if [ "$OS" == "linux" ]; then
cat > installer_build/systemd/loco-agent.service << 'EOF'
[Unit]
Description=LoCo Agent Server
After=network.target

[Service]
Type=simple
User=%i
WorkingDirectory=%h/.config/loco-agent
ExecStart=/opt/loco-agent/bin/loco-agent
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi

# Create install script
cat > installer_build/install.sh << 'EOF'
#!/bin/bash
# LoCo Agent Installer

set -e

echo "================================"
echo "LoCo Agent Server - Installer"
echo "================================"
echo

# Check for root (for system-wide install)
if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/opt/loco-agent"
    SYSTEMD_DIR="/etc/systemd/system"
    echo "Installing system-wide to ${INSTALL_DIR}"
else
    INSTALL_DIR="${HOME}/.local/share/loco-agent"
    SYSTEMD_DIR="${HOME}/.config/systemd/user"
    echo "Installing for current user to ${INSTALL_DIR}"
fi

# Create directories
mkdir -p "${INSTALL_DIR}"/{bin,config,scripts}

# Copy files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "${SCRIPT_DIR}"/bin/* "${INSTALL_DIR}/bin/"
cp -r "${SCRIPT_DIR}"/config/* "${INSTALL_DIR}/config/"
cp -r "${SCRIPT_DIR}"/scripts/* "${INSTALL_DIR}/scripts/"

# Make executable
chmod +x "${INSTALL_DIR}/bin/loco-agent"
chmod +x "${INSTALL_DIR}/scripts/start-loco.sh"

# Install systemd service (Linux only)
if [ -f "${SCRIPT_DIR}/systemd/loco-agent.service" ]; then
    mkdir -p "${SYSTEMD_DIR}"
    cp "${SCRIPT_DIR}/systemd/loco-agent.service" "${SYSTEMD_DIR}/"
    
    if [ "$EUID" -eq 0 ]; then
        systemctl daemon-reload
        echo "Service installed. Enable with: systemctl enable loco-agent@<username>"
    else
        systemctl --user daemon-reload
        echo "Service installed. Enable with: systemctl --user enable loco-agent"
    fi
fi

# Create symlink to launcher
if [ "$EUID" -eq 0 ]; then
    ln -sf "${INSTALL_DIR}/scripts/start-loco.sh" /usr/local/bin/loco-agent
else
    mkdir -p "${HOME}/.local/bin"
    ln -sf "${INSTALL_DIR}/scripts/start-loco.sh" "${HOME}/.local/bin/loco-agent"
    echo "Add ${HOME}/.local/bin to your PATH to run 'loco-agent' from anywhere"
fi

echo
echo "Installation complete!"
echo
echo "To start LoCo Agent:"
echo "  Run: loco-agent"
echo
echo "To configure:"
echo "  Edit: ${HOME}/.config/loco-agent/.env"
echo
echo "To run as service:"
if [ "$EUID" -eq 0 ]; then
    echo "  systemctl enable loco-agent@<username>"
    echo "  systemctl start loco-agent@<username>"
else
    echo "  systemctl --user enable loco-agent"
    echo "  systemctl --user start loco-agent"
fi
echo
EOF
chmod +x installer_build/install.sh

# Create uninstall script
cat > installer_build/uninstall.sh << 'EOF'
#!/bin/bash
# LoCo Agent Uninstaller

set -e

echo "Uninstalling LoCo Agent..."

if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/opt/loco-agent"
    systemctl stop loco-agent@* 2>/dev/null || true
    systemctl disable loco-agent@* 2>/dev/null || true
    rm -f /etc/systemd/system/loco-agent.service
    rm -f /usr/local/bin/loco-agent
else
    INSTALL_DIR="${HOME}/.local/share/loco-agent"
    systemctl --user stop loco-agent 2>/dev/null || true
    systemctl --user disable loco-agent 2>/dev/null || true
    rm -f "${HOME}/.config/systemd/user/loco-agent.service"
    rm -f "${HOME}/.local/bin/loco-agent"
fi

rm -rf "${INSTALL_DIR}"

echo "Uninstall complete!"
echo
echo "Note: Configuration and data remain at:"
echo "  ${HOME}/.config/loco-agent"
echo "  ${HOME}/.local/share/loco-agent/data"
echo
EOF
chmod +x installer_build/uninstall.sh

# Create README
cat > installer_build/README.md << 'EOF'
# LoCo Agent Server

Local-first coding agent server with agentic RAG and ACE.

## Installation

```bash
./install.sh
```

This will:
- Install LoCo Agent to `/opt/loco-agent` (system-wide) or `~/.local/share/loco-agent` (user)
- Create default configuration at `~/.config/loco-agent/.env`
- Set up systemd service (Linux only)
- Create `loco-agent` command

## Quick Start

1. Install dependencies:
   ```bash
   # Install Ollama
   curl https://ollama.ai/install.sh | sh
   
   # Pull a model
   ollama pull qwen2.5-coder:7b
   
   # Install Docker (for Qdrant)
   # Follow: https://docs.docker.com/engine/install/
   ```

2. Start Qdrant:
   ```bash
   docker run -d -p 6333:6333 qdrant/qdrant
   ```

3. Run LoCo Agent:
   ```bash
   loco-agent
   ```

## Configuration

Edit `~/.config/loco-agent/.env`:
- `PORT`: Server port (default: 3199)
- `MODEL_PROVIDER`: ollama, vllm, or llamacpp
- `MODEL_NAME`: Model to use
- `DATABASE_URL`: Database location

## Run as Service (Linux)

```bash
# User service
systemctl --user enable loco-agent
systemctl --user start loco-agent

# System service (requires root install)
sudo systemctl enable loco-agent@username
sudo systemctl start loco-agent@username
```

## Uninstall

```bash
./uninstall.sh
```

## Logs

```bash
# If running as service
journalctl --user -u loco-agent -f

# Or
journalctl -u loco-agent@username -f
```

## API

Access at `http://localhost:3199`

See API documentation at `http://localhost:3199/docs`
EOF

echo "[6/6] Creating self-extracting installer..."
mkdir -p releases

if [ "$OS" == "linux" ]; then
    # Create self-extracting archive for Linux
    ARCHIVE_NAME="LoCoAgent-Server-Linux.run"
    
    cat > installer_build/extract_and_run.sh << 'EOF'
#!/bin/bash
# Self-extracting installer
ARCHIVE=`awk '/^__ARCHIVE_BELOW__/ {print NR + 1; exit 0; }' $0`
tail -n+$ARCHIVE $0 | tar xzv -C /tmp
cd /tmp/loco-agent-installer
./install.sh
exit 0
__ARCHIVE_BELOW__
EOF
    
    cd installer_build
    tar czf - * > ../releases/${ARCHIVE_NAME}.tar.gz
    cd ..
    cat installer_build/extract_and_run.sh releases/${ARCHIVE_NAME}.tar.gz > releases/${ARCHIVE_NAME}
    chmod +x releases/${ARCHIVE_NAME}
    rm releases/${ARCHIVE_NAME}.tar.gz
    
    echo
    echo "================================"
    echo "Build Complete!"
    echo "================================"
    echo
    echo "Installer: releases/${ARCHIVE_NAME}"
    echo
    echo "To install:"
    echo "  ./releases/${ARCHIVE_NAME}"
    echo
    
else
    # Create tar.gz for macOS (would need to create .pkg with pkgbuild)
    ARCHIVE_NAME="LoCoAgent-Server-macOS.tar.gz"
    
    cd installer_build
    tar czf ../releases/${ARCHIVE_NAME} *
    cd ..
    
    echo
    echo "================================"
    echo "Build Complete!"
    echo "================================"
    echo
    echo "Archive: releases/${ARCHIVE_NAME}"
    echo
    echo "To install:"
    echo "  tar xzf releases/${ARCHIVE_NAME}"
    echo "  cd loco-agent-installer"
    echo "  ./install.sh"
    echo
fi

echo "The installer will:"
echo "- Install LoCo Agent binary"
echo "- Set up configuration directory"
echo "- Create systemd service (Linux)"
echo "- Add 'loco-agent' command"
echo
