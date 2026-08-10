#!/usr/bin/env bash
# One-click launcher for macOS / Linux.
# Creates a virtual environment, installs dependencies, and starts the app.
set -e

cd "$(dirname "$0")"

# Pick a Python 3 interpreter.
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

# Create the virtual environment on first run.
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv .venv
fi

# Activate it.
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

echo "Starting the AI Data Readiness Auditor..."
python -m streamlit run app.py
