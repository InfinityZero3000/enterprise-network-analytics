#!/bin/bash

echo "============================================="
echo "🚀 Starting Enterprise Network Analytics..."
echo "============================================="

# Start Docker containers in the background
echo "📦 Starting Backend and Database services via Docker Compose..."
docker compose up -d

echo ""
echo "🌐 Starting Web UI development server..."
echo "Press Ctrl+C to stop the Web UI (Docker services will remain running in the background)."
echo ""

# Navigate to the UI directory and start the frontend
cd ui && npm run dev
