#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -d ".venv" ]]; then
	echo "Error: .venv not found at $SCRIPT_DIR/.venv"
	echo "Create it first with: python3 -m venv .venv"
	exit 1
fi

source .venv/bin/activate
nohup python run.py >/dev/null 2>&1 &
PID=$!
echo "ATBIS started in background (PID: $PID)"
