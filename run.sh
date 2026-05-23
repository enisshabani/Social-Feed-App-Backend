#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Prefer the project-level virtualenv first, then common local fallbacks.
if [ -x "$SCRIPT_DIR/../venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/../venv/bin/python"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
else
    PYTHON_BIN="python3"
fi

# 1. Aktivizo mjedisin virtual (nëse ekziston)
if [ -d "$SCRIPT_DIR/../venv" ]; then
    echo "Duke aktivizuar mjedisin virtual (../venv)..."
    source "$SCRIPT_DIR/../venv/bin/activate"
elif [ -d "$SCRIPT_DIR/.venv" ]; then
    echo "Duke aktivizuar mjedisin virtual (.venv)..."
    source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -d "$SCRIPT_DIR/venv" ]; then
    echo "Duke aktivizuar mjedisin virtual (venv)..."
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# 2. Sigurohu që variablat e mjedisit janë gati
if [ ! -f "$SCRIPT_DIR/.env" ] && [ -f "$SCRIPT_DIR/.env.example" ]; then
    echo "Kujdes: .env nuk u gjet. Duke krijuar një kopje nga .env.example..."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
fi

# 3. Nis serverin FastAPI me Uvicorn
# --host 0.0.0.0 e bën të aksesueshëm në rrjet
# --port 8000 është porti standard
# --reload bën që serveri të rifreskohet automatikisht kur ndryshon kodin
echo "Duke nisur Backend-in..."
cd "$SCRIPT_DIR"
"$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload