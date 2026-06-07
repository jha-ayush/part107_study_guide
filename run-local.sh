#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
echo "Part 107 Ground School at http://127.0.0.1:8000  (Ctrl+C to stop)"
python app.py
