#!/bin/bash
# Data Visualization Copilot — Start Script
set -e

echo "🚀 Starting Data Visualization Copilot..."
cd "$(dirname "$0")"

# Create .env if missing
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  Created .env from template — add your GROQ_API_KEY"
fi

# 1. Setup Virtual Environment
if [ ! -d "venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv venv
fi

echo "🔌 Activating virtual environment..."
source venv/bin/activate

# 2. Install Python deps
echo "📥 Installing/Updating dependencies..."
pip install -q -r requirements.txt
pip install -q qdrant-client fastembed redis  # Ensure new memory deps are present

# Build frontend if not already built
if [ ! -f backend/static/index.html ]; then
  echo "⚙️  Building frontend (first time)..."
  cd frontend && npm install --silent 2>/dev/null && npx vite build --silent 2>/dev/null && cd ..
  echo "✅ Frontend built"
fi

mkdir -p uploads

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Data Visualization Copilot"
echo "  Open in browser → http://localhost:8001"
echo "  API Docs        → http://localhost:8001/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PYTHONPATH=. python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
