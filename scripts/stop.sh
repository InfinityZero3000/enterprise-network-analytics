#!/bin/bash

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

echo "============================================="
echo "Stopping Enterprise Network Analytics..."
echo "============================================="

echo "Stopping Web UI development server..."
pkill -f "vite"
if [ $? -eq 0 ]; then
    echo "Web UI stopped successfully."
else
    echo "Web UI was already stopped."
fi

echo ""
echo "Stopping Backend and Database services via Docker Compose..."
docker compose down

echo ""
echo "============================================="
echo "All services stopped successfully!"
echo "============================================="
