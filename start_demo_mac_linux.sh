#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -e .
if [ ! -f demo_project/deckforge.json ]; then .venv/bin/python -m deckforge demo demo_project; fi
.venv/bin/python -m deckforge build demo_project
.venv/bin/python -m deckforge verify demo_project/build/deckforge_package.zip
echo 'Open demo_project/build/qa_dashboard.html in your browser.'
