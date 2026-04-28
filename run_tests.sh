#!/usr/bin/env bash
# Esegui la test suite PDFusion
# Uso: bash run_tests.sh [opzioni pytest]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "Ambiente virtuale non trovato. Esegui prima start.sh." >&2
  exit 1
fi

cd "$SCRIPT_DIR"

# Su Linux imposta DISPLAY per i test Qt (headless)
if [[ "$(uname)" == "Linux" ]] && [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  export QT_QPA_PLATFORM=offscreen
fi

exec "$VENV_PYTHON" -m pytest tests/ -v --tb=short "$@"
