#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m pip install -q -r requirements.txt
export PORT="${PORT:-8000}"
echo "Open http://localhost:$PORT"
exec python app.py
