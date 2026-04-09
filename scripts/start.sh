#!/bin/bash

set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

command_exists() {
	command -v "$1" >/dev/null 2>&1
}

need_command() {
	local cmd="$1"
	local hint="$2"
	if ! command_exists "$cmd"; then
		echo "[ERROR] Missing dependency: $cmd"
		echo "        $hint"
		exit 1
	fi
}

echo "============================================="
echo "Starting Enterprise Network Analytics..."
echo "============================================="

echo "Checking required dependencies..."
need_command docker "Please install Docker Engine first."
need_command npm "Please install Node.js and npm first."

if ! docker info >/dev/null 2>&1; then
	echo "[ERROR] Docker daemon is not running."
	echo "        Start Docker and run this script again."
	exit 1
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
	echo "No .env found. Creating from .env.example ..."
	cp .env.example .env
fi

if [ ! -d "ui/node_modules" ]; then
	echo "UI dependencies not found. Installing..."
	cd ui
	if [ -f "package-lock.json" ]; then
		npm ci
	else
		npm install
	fi
	cd "$DIR"
fi

echo "Starting Backend and Database services via Docker Compose..."
docker compose up -d

echo ""
echo "Starting Web UI development server in the background..."
cd ui
nohup npm run dev > ui.log 2>&1 &
cd "$DIR"
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
