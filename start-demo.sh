#!/usr/bin/env bash
set -Eeuo pipefail
DEMO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DEMO_ROOT"
[[ -f .env ]] || { echo "Missing .env. Copy .env.example and run ./prepare-demo.sh first."; exit 1; }
[[ -x backend/.venv/bin/python ]] || { echo "Backend dependencies missing. See README."; exit 1; }
[[ -x frontend/node_modules/.bin/vite ]] || { echo "Frontend dependencies missing. See README."; exit 1; }
[[ -f frontend/dist/index.html ]] || { echo "Frontend build missing. Run ./prepare-demo.sh."; exit 1; }
command -v setsid >/dev/null || { echo "This launcher requires Linux setsid. See README for separate-process startup."; exit 1; }
backend/.venv/bin/python scripts/prepare-demo.py --check-only
backend/.venv/bin/python scripts/demo-runtime-check.py --check-ports
DEMO_FRONTEND_PORT="$(backend/.venv/bin/python scripts/demo-runtime-check.py --ports)"
children=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${children[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  wait || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
setsid backend/.venv/bin/python scripts/start-demo-backend.py &
children+=("$!")
(cd frontend && exec setsid npm run preview -- --host 127.0.0.1 --port "$DEMO_FRONTEND_PORT" --strictPort) &
children+=("$!")
backend/.venv/bin/python scripts/demo-runtime-check.py --timeout 45
if [[ "${OPEN_BROWSER:-0}" == "1" ]] && command -v xdg-open >/dev/null; then
  xdg-open "http://127.0.0.1:$DEMO_FRONTEND_PORT/dashboard?demo=1" >/dev/null 2>&1 || true
fi
echo "Ctrl+C stops backend and frontend. PostgreSQL and historical archives are retained."
wait -n "${children[@]}"
