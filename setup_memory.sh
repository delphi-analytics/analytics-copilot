#!/bin/bash
echo "🚀 Setting up Agent Memory Management Infrastructure..."

# 1. Start Docker Compose services
echo "📦 Starting PostgreSQL, Redis, and Qdrant..."
sudo docker compose --profile vector up -d postgres redis qdrant

# 2. Install Python dependencies
echo "🐍 Installing memory dependencies..."
source venv/bin/activate
pip install qdrant-client fastembed

echo "✅ Setup complete! Database endpoints are exposed locally."
