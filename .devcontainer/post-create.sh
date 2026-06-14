#!/bin/bash
set -e

echo "=== Installing project dependencies ==="

# Python dependencies
echo "[Python] Installing requirements..."
python3 -m pip install --no-cache-dir -r requirements.txt

# Root npm dependencies (concurrently)
echo "[Node] Installing root dependencies..."
npm install

# Frontend dependencies
echo "[Node] Installing frontend dependencies..."
cd frontend && npm install && cd ..

# Go dependencies
echo "[Go] Downloading modules..."
cd backend/boss_service && go mod download && cd ../..

echo ""
echo "=== All dependencies installed! ==="
echo ""
echo "Run 'npm start' to launch all services."
