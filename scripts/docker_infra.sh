#!/usr/bin/env bash
# Docker Compose helpers (full stack: postgres, redis, backend, agent, frontend).
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
cmd="${1:-up}"
case "${cmd}" in
  up)
    docker compose up -d --build
    echo "Backend API:  http://localhost:${BACKEND_PUBLISH_PORT:-8000}"
    echo "Frontend:     http://localhost:${FRONTEND_PUBLISH_PORT:-3000}"
    echo "Drive MCP:    http://localhost:${MCP_DRIVE_PUBLISH_PORT:-8787}/health"
    echo "Postgres:     localhost:${POSTGRES_PUBLISH_PORT:-5432}  (user=taskbot db=taskbot)"
    echo "Redis:        localhost:${REDIS_PUBLISH_PORT:-6379}"
    ;;
  up-db)
    docker compose up -d postgres redis
    ;;
  down)
    docker compose down
    ;;
  down-volumes)
    docker compose down -v
    ;;
  logs)
    docker compose logs -f "${@:2}"
    ;;
  ps)
    docker compose ps
    ;;
  build)
    docker compose build "${@:2}"
    ;;
  *)
    echo "Usage: $0 [up|up-db|down|down-volumes|logs|ps|build]"
    exit 1
    ;;
esac
