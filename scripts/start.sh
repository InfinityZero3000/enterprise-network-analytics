#!/bin/bash

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

echo "============================================="
echo "Starting Enterprise Network Analytics..."
echo "============================================="

echo "Starting Backend and Database services via Docker Compose..."
docker compose up -d

echo ""
echo "Starting Web UI development server in the background..."
cd ui && nohup npm run dev > ui.log 2>&1 &
echo "Web UI logs are being saved to ui/ui.log"

echo ""
echo "============================================="
echo "All services started successfully!"
echo ""
echo "Useful Endpoints & Ports:"
echo " - Web UI:       http://localhost:5173"
echo " - API Backend:  http://localhost:8000"
echo " - Neo4j UI:     http://localhost:7474 (Bolt: 7687)"
echo " - Kafka UI:     http://localhost:8080"
echo " - MLflow UI:    http://localhost:5000"
echo " - MinIO UI:     http://localhost:9001 (API: 9000)"
echo " - Spark UI:     http://localhost:8082"
echo ""
echo "Use 'sh scripts/stop.sh' to stop everything at once."
echo "============================================="
