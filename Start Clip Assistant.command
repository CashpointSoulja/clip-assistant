#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
python3 server.py &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' INT TERM EXIT
(sleep 2; open http://127.0.0.1:8765) &
wait "$PID"
