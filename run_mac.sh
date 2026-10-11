#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Virtual environment not found. Run ./setup_mac.sh first."
  exit 1
fi
if [ ! -f .env ]; then
  echo ".env not found. Run ./setup_mac.sh and configure it before starting."
  exit 1
fi
source .venv/bin/activate
python run.py
