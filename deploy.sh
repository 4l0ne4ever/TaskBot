#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/taskExtractor"
BACKEND_DIR="$PROJECT_ROOT/backend-api"
AGENT_DIR="$PROJECT_ROOT/agent-module"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "==> Pull latest code"
cd "$PROJECT_ROOT"
git pull

echo "==> Backend dependencies and migrations"
cd "$BACKEND_DIR"
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

echo "==> Agent dependencies"
cd "$AGENT_DIR"
source venv/bin/activate
pip install -r requirements.txt

echo "==> Frontend build and restart"
cd "$FRONTEND_DIR"
npm install
npm run build
pm2 restart taskbot-frontend || pm2 start npm --name taskbot-frontend -- start

echo "==> Restart AWS-native services"
sudo systemctl restart taskbot-backend-api
sudo systemctl restart taskbot-agent-worker
sudo systemctl restart nginx

echo "==> Service status"
sudo systemctl --no-pager --full status taskbot-backend-api taskbot-agent-worker nginx || true
pm2 status
