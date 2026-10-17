#!/usr/bin/env bash
set -Eeuo pipefail
DEMO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_ROOT"
[[ -f .env && -x backend/.venv/bin/python ]] || { echo "Configure .env and backend/.venv first."; exit 1; }
exec backend/.venv/bin/python scripts/demo-db.py backup "$@"
