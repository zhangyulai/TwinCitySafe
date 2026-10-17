#!/usr/bin/env bash
# Record a continuous real browser session against the running local demo.
set -Eeuo pipefail

DEMO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_ROOT"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required." >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe is required." >&2; exit 1; }
echo "Recording real browser actions for five minutes. Keep the demo service running."
echo "This runs software Flood/Leak scenarios and resets them while retaining history."
echo "Requires normal monitoring at start and existing CLOSED Flood/Leak archives."
node frontend/scripts/record-live-demo.cjs --narrated
python3 scripts/render-narrated-demo.py
