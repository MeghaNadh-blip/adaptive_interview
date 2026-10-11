#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit .env with SECRET_KEY, MONGO_URI, and at least one AI provider key, then run ./run_mac.sh."
else
  echo "Existing .env preserved. Keep it private."
  echo "Setup complete. Start with ./run_mac.sh"
fi
