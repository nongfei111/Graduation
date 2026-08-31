#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p logs

if [ -f "$SCRIPT_DIR/.env.pi" ]; then
  set -a
  . "$SCRIPT_DIR/.env.pi"
  set +a
fi

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/aaa/.Xauthority}"

export LIVENESS_FRAME_COUNT=4
export LIVENESS_MIN_FRAMES=3
export LIVENESS_CAPTURE_INTERVAL_SEC=0.15
export LIVENESS_TIMEOUT_SEC=5
export LIVENESS_PASS_SCORE_STRICT=0.58
export RECOGNITION_INTERVAL_SEC=3

PYTHON_BIN="python3"
if [ "${USE_VENV:-0}" = "1" ] && [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
fi

exec "$PYTHON_BIN" main.py
