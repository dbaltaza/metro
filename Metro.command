#!/bin/bash
# Double-click this file in Finder to play from the source checkout.
# It creates the virtual environment on first run, then starts the game.
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "Setting up for the first time..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/python init.py
