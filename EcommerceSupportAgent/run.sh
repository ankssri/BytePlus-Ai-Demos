#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: neither python3 nor python is on PATH. Install Python 3.10+ (e.g. 'brew install python')." >&2
  exit 1
fi

VENV=".venv"
if [ ! -d "$VENV" ]; then
  echo "Creating virtualenv in $VENV ..."
  "$PY" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install --upgrade pip >/dev/null
python -m pip install -q -r requirements.txt

export PORT="${PORT:-8000}"
echo "Open http://localhost:$PORT"
exec python app.py
