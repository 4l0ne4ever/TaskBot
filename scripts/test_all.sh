#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing .venv. Create it first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Running backend-api tests..."
"${PYTHON_BIN}" -m pytest "${ROOT_DIR}/backend-api/tests" -c "${ROOT_DIR}/backend-api/pytest.ini" -q

echo "Running agent-module tests..."
"${PYTHON_BIN}" -m pytest "${ROOT_DIR}/agent-module/tests" -c "${ROOT_DIR}/agent-module/pytest.ini" -q
