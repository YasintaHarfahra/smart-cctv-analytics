#!/bin/bash
set -e

echo "🔨 Build backend image..."
docker compose build backend

echo "🚀 Starting backend container..."
docker compose up -d backend

echo "⏳ Tunggu 5 detik biar backend siap..."
sleep 5

echo "📜 Logs backend:"
docker logs --tail=20 my_backend

echo "🩺 Testing health endpoint..."
curl -s http://localhost:8000/health || echo "❌ Backend belum siap!"
