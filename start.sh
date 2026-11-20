#!/usr/bin/env bash
# Start Study Buddy on Mac / Linux:   bash start.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "First run: setting things up, this takes a minute..."
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
echo "Starting Study Buddy... your browser will open. Press Ctrl+C to stop."
python -m streamlit run app.py
