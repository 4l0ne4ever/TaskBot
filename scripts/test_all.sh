#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing .venv. Create it first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Running backend tests..."
"${PYTHON_BIN}" -m pytest "${ROOT_DIR}/backend/tests" -c "${ROOT_DIR}/backend/pytest.ini" -q

echo "Running agent tests..."
"${PYTHON_BIN}" -m pytest "${ROOT_DIR}/agent/tests" -c "${ROOT_DIR}/agent/pytest.ini" -q

echo "Running drive-mcp-server tests..."
"${PYTHON_BIN}" -m pytest "${ROOT_DIR}/drive-mcp-server/tests" -c "${ROOT_DIR}/drive-mcp-server/pytest.ini" -q
