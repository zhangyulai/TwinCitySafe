#!/usr/bin/env bash
# Continuous local browser recording; no screenshot inputs.
set -Eeuo pipefail
DEMO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_ROOT"
echo "Recording all six modules, software scenarios and incident work-order closure."
echo "Requires running demo services, no active incident, and an existing closed Flood archive."
echo "Narration must already exist in docs/video/seven/voice/manifest.json."
test -f docs/video/seven/voice/manifest.json
node frontend/scripts/record-live-demo.cjs --seven
python3 scripts/render-narrated-demo.py --seven
