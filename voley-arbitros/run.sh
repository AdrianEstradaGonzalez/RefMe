#!/usr/bin/env bash
# Arranque rápido del servidor de desarrollo.
set -e

cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual..."
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Instalando dependencias..."
pip install -q -r requirements.txt

echo "Arrancando servidor en http://127.0.0.1:8000 ..."
uvicorn app.main:app --reload
