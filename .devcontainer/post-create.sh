#!/bin/bash
set -e

echo "=== Installing project dependencies ==="

# Python dependencies (--break-system-packages is safe inside devcontainer)
echo "[Python] Installing requirements..."
python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Root npm dependencies (concurrently)
echo "[Node] Installing root dependencies..."
npm install

# Frontend dependencies
echo "[Node] Installing frontend dependencies..."
cd frontend && npm install && cd ..

# Go dependencies
echo "[Go] Downloading modules..."
cd backend/boss_service && go mod download && cd ../..

# gRPC stubs (Inventory Service)
echo "[gRPC] Generating stubs from inventory.proto..."
cd backend/inventory_service
python3 -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/inventory.proto
cd ../..
# RabbitMQ
echo "[RabbitMQ] Iniciando servidor..."
sudo rabbitmq-server -detached
sleep 3
sudo rabbitmq-plugins enable rabbitmq_management > /dev/null 2>&1
echo "[RabbitMQ] Pronto! UI em http://localhost:15672 (guest/guest)"

# Install aio-pika
echo "[Python] Installing aio-pika..."
python3 -m pip install --no-cache-dir --break-system-packages aio-pika

echo ""
echo "=== All dependencies installed! ==="
echo ""
echo "Run 'npm start' to launch all services."
echo "RabbitMQ UI: http://localhost:15672 (guest/guest)"
