# Quick Start Guide

Get LoCo Agent up and running in 10 minutes.

## Step 1: Install Prerequisites

### Required:
- **Python 3.10+**: [Download](https://www.python.org/downloads/)
- **Node.js 18+**: [Download](https://nodejs.org/)
- **Docker**: [Download](https://www.docker.com/products/docker-desktop/)
- **Ollama**: [Download](https://ollama.ai/)

### Install Ollama Model:
```bash
ollama pull qwen3-coder:30b-a3b-q4_K_M
```

## Step 2: Start Qdrant

```bash
cd project
docker compose up -d qdrant

# Verify it's running
curl http://localhost:6333/health
```

## Step 3: Set Up Server

```bash
cd server

# Create virtual environment
python3 -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env if needed (defaults should work)

# Start server
python -m uvicorn app.main:app --reload --port 3199
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:3199
INFO:     Application startup complete.
```

**Keep this terminal open!**

## Step 4: Set Up Extension

Open a **new terminal**:

```bash
cd extension

# Install dependencies
npm install

# Compile TypeScript
npm run compile
```

## Step 5: Launch Extension

1. Open the `extension/` folder in VS Code:
   ```bash
   code .
   ```

2. Press `F5` to launch the Extension Development Host

3. In the new VS Code window, open a project folder

4. Click the LoCo Agent icon in the Activity Bar (left sidebar)

## Step 6: Configure (First Time)

In VS Code settings (`Ctrl+,` or `Cmd+,`):

Search for "LoCo Agent" and verify:
- **Server URL**: `http://localhost:3199`
- **Model Provider**: `ollama`
- **Model Name**: `qwen3-coder:30b-a3b-q4_K_M`
- **Auto Context**: `true` (enabled)

## Step 7: Test It!

1. In the LoCo Agent sidebar, type:
   ```
   Hello! Can you see my workspace?
   ```

2. You should get a response from the agent

3. Try a slash command:
   ```
   /explain
   ```

4. Open a file with code and try:
   ```
   Fix any issues in this file
   ```

## Troubleshooting

### "Cannot connect to server"

Check that the server is running:
```bash
curl http://localhost:3199/v1/health
```

Should return:
```json
{"status":"healthy","version":"0.1.0","protocol_version":"1.0.0"}
```

### "Failed to connect to Qdrant"

Check Qdrant is running:
```bash
docker ps | grep qdrant
curl http://localhost:6333/health
```

Restart if needed:
```bash
docker compose restart qdrant
```

### "Ollama model not found"

Pull the model:
```bash
ollama pull qwen3-coder:30b-a3b-q4_K_M
ollama list  # Verify it's installed
```

### Extension not loading

1. Check the Extension Development Host console (Help → Toggle Developer Tools)
2. Look for errors in the output
3. Try recompiling: `npm run compile`
4. Restart the Extension Development Host (`Ctrl+R` or `Cmd+R`)

## Next Steps

### Try These Commands:

- `/fix` - Fix errors in current file
- `/explain` - Explain selected code
- `/test` - Generate tests
- `/refactor` - Refactor code

### Use @ Mentions:

- `@filename` - Include a specific file
- `@symbol` - Include a function or class
- `@problems` - Include all diagnostics

### Example Workflows:

1. **Fix a Bug:**
   ```
   /fix the authentication bug in login.ts
   ```

2. **Explain Code:**
   Select code → Right-click → "Ask LoCo Agent"

3. **Generate Tests:**
   ```
   /test the validatePassword function
   ```

4. **Refactor:**
   ```
   /refactor this component to use React hooks
   ```

## Configuration Options

### Server (.env)

```bash
# Use a different model
MODEL_NAME=qwen3-coder:30b-a3b-q4_K_M

# Change port
PORT=3200

# Enable/disable features
DEBUG=false
```

### Extension (VS Code Settings)

```json
{
  "locoAgent.serverUrl": "http://localhost:3199",
  "locoAgent.autoContext": true,
  "locoAgent.showInlineDiffs": true,
  "locoAgent.autoApproveSimple": false
}
```

## What's Working vs. Coming Soon

### ✅ Working Now:
- Chat interface with streaming responses
- Automatic context gathering (files, diagnostics, git)
- Diff preview and application
- WebSocket communication
- Database and session management

### 🚧 Coming Soon:
- Full indexing pipeline
- Vector search (Qdrant integration)
- Agentic RAG retrieval
- Slash command handlers
- @ mention pickers
- Iterative fix loops
- ACE artifact system

## Getting Help

- **Logs**: Check server terminal for errors
- **Extension Logs**: Help → Toggle Developer Tools → Console
- **Database**: SQLite file at `server/loco_agent.db`
- **Documentation**: See `docs/` folder

## Development Mode

To work on the extension:

1. Make changes to TypeScript files
2. Run `npm run compile` (or `npm run watch` for auto-compile)
3. Reload extension (`Ctrl+R` or `Cmd+R` in Extension Development Host)

To work on the server:

1. Server auto-reloads when you save Python files (thanks to `--reload`)
2. Check logs in the terminal

---

**Welcome to LoCo Agent!** 🚀

You now have a local-first coding agent running on your machine.
