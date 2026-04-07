#!/usr/bin/env bash
# Build and start the full Docker Compose stack, then smoke-check each service.
#
# Compose interpolates POSTGRES_PUBLISH_PORT / REDIS_PUBLISH_PORT from a root `.env` file if present.
# If `docker compose up` fails with "address already in use" on 5432/6379, set those variables in `.env`
# (see `.env.example`) or export them for this run, e.g. POSTGRES_PUBLISH_PORT=55432 REDIS_PUBLISH_PORT=56379
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BACKEND_PORT="${BACKEND_PUBLISH_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PUBLISH_PORT:-3000}"
MCP_DRIVE_PORT="${MCP_DRIVE_PUBLISH_PORT:-8787}"
POSTGRES_PORT="${POSTGRES_PUBLISH_PORT:-5432}"
REDIS_PORT="${REDIS_PUBLISH_PORT:-6379}"

echo "==> docker compose up -d --build"
docker compose up -d --build

echo "==> Wait for backend /health (up to ~120s)"
ok=0
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 3
done
if [[ "${ok}" -ne 1 ]]; then
  echo "ERR backend /health did not become ready"
  docker compose ps
  docker compose logs --tail=80 backend || true
  exit 1
fi
echo "OK  backend http://127.0.0.1:${BACKEND_PORT}/health"

echo "==> Postgres (pg_isready in container)"
docker compose exec -T postgres pg_isready -U taskbot -d taskbot
echo "OK  postgres"

echo "==> Redis PING"
docker compose exec -T redis redis-cli ping
echo "OK  redis"

echo "==> Drive MCP /health"
if curl -sf "http://127.0.0.1:${MCP_DRIVE_PORT}/health" >/dev/null 2>&1; then
  echo "OK  mcp-drive http://127.0.0.1:${MCP_DRIVE_PORT}/health"
else
  echo "ERR mcp-drive /health"
  docker compose logs --tail=40 mcp-drive || true
  exit 1
fi

echo "==> Agent container running"
docker compose ps agent | grep -q Up || { echo "ERR agent not Up"; docker compose logs --tail=40 agent; exit 1; }
echo "OK  agent (container Up)"

echo "==> Frontend (optional: Next dev may take time)"
sleep 5
if curl -sf "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null 2>&1; then
  echo "OK  frontend http://127.0.0.1:${FRONTEND_PORT}"
else
  echo "WARN frontend not responding yet on :${FRONTEND_PORT} (next dev may still compile; check: docker compose logs frontend)"
fi

echo ""
echo "All critical checks passed (frontend may still be warming up)."
docker compose ps
