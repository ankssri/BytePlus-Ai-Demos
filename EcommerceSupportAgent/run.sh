#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Prefer python3 (macOS default); fall back to python if that's what's on PATH.
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: neither python3 nor python is on PATH. Install Python 3.10+ (e.g. 'brew install python')." >&2
  exit 1
fi

"$PY" -m pip install -q --user -r requirements.txt || "$PY" -m pip install -q -r requirements.txt
export PORT="${PORT:-8000}"
echo "Open http://localhost:$PORT"
exec "$PY" app.py
