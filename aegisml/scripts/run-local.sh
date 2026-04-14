#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python -m pip install -q -e ".[dev]"
export AEGISML_PORT="${AEGISML_PORT:-8080}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${AEGISML_PORT}"
