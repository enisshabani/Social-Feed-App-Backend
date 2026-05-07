#!/bin/bash

# 1. Aktivizo mjedisin virtual (nëse ekziston)
if [ -d ".venv" ]; then
    echo "Duke aktivizuar mjedisin virtual (.venv)..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Duke aktivizuar mjedisin virtual (venv)..."
    source venv/bin/activate
fi

# 2. Sigurohu që variablat e mjedisit janë gati
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Kujdes: .env nuk u gjet. Duke krijuar një kopje nga .env.example..."
    cp .env.example .env
fi

# 3. Nis serverin FastAPI me Uvicorn
# --host 0.0.0.0 e bën të aksesueshëm në rrjet
# --port 8000 është porti standard
# --reload bën që serveri të rifreskohet automatikisht kur ndryshon kodin
echo "Duke nisur Backend-in..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload