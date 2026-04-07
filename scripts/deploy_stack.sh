#!/usr/bin/env bash
# Deploy TaskBot on a host using Docker Compose (EC2 or any Linux server with Docker).
# Set TASKBOT_ROOT to the clone path if not using the default.
set -euo pipefail
TASKBOT_ROOT="${TASKBOT_ROOT:-/home/ubuntu/taskExtractor}"
cd "${TASKBOT_ROOT}"

echo "==> Git pull"
git pull

echo "==> Build and start stack"
docker compose build
docker compose up -d

echo "==> Status"
docker compose ps

echo "Done. Ensure .env exists on the server and host firewall allows published ports (80/443 via reverse proxy recommended)."
