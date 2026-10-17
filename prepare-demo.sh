#!/usr/bin/env bash
set -Eeuo pipefail
DEMO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DEMO_ROOT"
[[ -f .env ]] || { echo "Missing .env: cp .env.example .env, then configure the local database."; exit 1; }
[[ -x backend/.venv/bin/python ]] || { echo "Backend dependencies missing. Follow README once before offline use."; exit 1; }
[[ -d frontend/node_modules ]] || { echo "Frontend dependencies missing. Run npm --prefix frontend ci before offline use."; exit 1; }
backend/.venv/bin/python scripts/prepare-demo.py
if [[ "${DEMO_BUILD:-1}" == "1" ]]; then
  npm --prefix frontend run build
else
  echo "Build skipped (DEMO_BUILD=0). start-demo.sh requires frontend/dist/index.html."
fi
echo "Preparation complete. No live state was reset and no history was deleted. Run ./start-demo.sh."
