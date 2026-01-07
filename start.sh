#!/bin/bash

# LoCo Agent Startup Script
# Starts Qdrant and Server together

set -e

echo "🚀 Starting LoCo Agent..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Start Qdrant
echo "📦 Starting Qdrant vector database..."
docker compose up -d qdrant

# Wait for Qdrant to be healthy
echo "⏳ Waiting for Qdrant to be ready..."
timeout=30
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if curl -f http://localhost:6333/health > /dev/null 2>&1; then
        echo "✅ Qdrant is healthy"
        break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

if [ $elapsed -ge $timeout ]; then
    echo "⚠️  Qdrant health check timed out, but continuing anyway..."
fi

# Start server
echo "🖥️  Starting server..."
cd backend

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Start server
echo "🚀 Server starting on http://localhost:3199"
echo ""
echo "   Health: http://localhost:3199/v1/health"
echo "   Qdrant: http://localhost:6333"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn app.main:app --reload --port 3199
