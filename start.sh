#!/usr/bin/env bash
# PDFusion — avvio su Linux e macOS
# Uso: bash start.sh  oppure  ./start.sh
set -euo pipefail

PYTHON_TARGET="3.13"
PYTHON_TARGET_MINOR=13
PYTHON_MIN_MINOR=11
PYTHON_MAX_MINOR=13

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

# Lingua
_LANG="${LANG:-${LANGUAGE:-en}}"
if [[ "$_LANG" == it* ]]; then
  MSG_CHECKING="Controllo ambiente..."
  MSG_PYTHON_FOUND="Python trovato:"
  MSG_PYTHON_NOT_FOUND="Python 3.11–3.13 non trovato. Installa Python 3.13 e riprova."
  MSG_VENV_CREATE="Creazione ambiente virtuale..."
  MSG_DEPS_INSTALL="Installazione dipendenze..."
  MSG_ALREADY_UP="Dipendenze già installate."
  MSG_STARTING="Avvio PDFusion..."
  MSG_PORT_BUSY="ATTENZIONE: porta 8080 occupata — potrebbe essere già in esecuzione."
else
  MSG_CHECKING="Checking environment..."
  MSG_PYTHON_FOUND="Python found:"
  MSG_PYTHON_NOT_FOUND="Python 3.11–3.13 not found. Install Python 3.13 and retry."
  MSG_VENV_CREATE="Creating virtual environment..."
  MSG_DEPS_INSTALL="Installing dependencies..."
  MSG_ALREADY_UP="Dependencies already installed."
  MSG_STARTING="Starting PDFusion..."
  MSG_PORT_BUSY="WARNING: port 8080 busy — PDFusion may already be running."
fi

# --- Trova Python ---
_RESOLVED_BIN=""
_RESOLVED_MINOR=0

_try_python() {
  local bin="$1"
  if command -v "$bin" &>/dev/null; then
    local ver
    ver="$("$bin" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo 0)"
    if (( ver >= PYTHON_MIN_MINOR && ver <= PYTHON_MAX_MINOR )); then
      _RESOLVED_BIN="$bin"
      _RESOLVED_MINOR="$ver"
      return 0
    fi
  fi
  return 1
}

echo "$MSG_CHECKING"

for candidate in \
    "python${PYTHON_TARGET}" \
    "python3.${PYTHON_TARGET_MINOR}" \
    "python3.12" "python3.11" \
    "python3" "python"; do
  _try_python "$candidate" && break || true
done

# pyenv fallback
if [ -z "$_RESOLVED_BIN" ] && [ -d "$HOME/.pyenv/versions" ]; then
  for pyenv_python in "$HOME/.pyenv/versions"/3.1[1-3]*/bin/python3; do
    [ -x "$pyenv_python" ] && _try_python "$pyenv_python" && break || true
  done
fi

if [ -z "$_RESOLVED_BIN" ]; then
  echo "$MSG_PYTHON_NOT_FOUND" >&2
  exit 1
fi

echo "$MSG_PYTHON_FOUND $_RESOLVED_BIN (3.$_RESOLVED_MINOR)"

# --- Ambiente virtuale ---
if [ ! -d "$VENV_DIR" ]; then
  echo "$MSG_VENV_CREATE"
  "$_RESOLVED_BIN" -m venv "$VENV_DIR"
fi

PYTHON_VENV="$VENV_DIR/bin/python"
PIP_VENV="$VENV_DIR/bin/pip"

if [ ! -f "$PYTHON_VENV" ]; then
  PYTHON_VENV="$VENV_DIR/bin/python3"
  PIP_VENV="$VENV_DIR/bin/pip3"
fi

# --- Dipendenze ---
REQ_HASH_FILE="$VENV_DIR/.req_hash"
REQ_HASH="$(sha256sum "$REQ_FILE" 2>/dev/null | cut -d' ' -f1 || echo "")"
SAVED_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")"

if [ "$REQ_HASH" != "$SAVED_HASH" ]; then
  echo "$MSG_DEPS_INSTALL"
  "$PIP_VENV" install --quiet --upgrade pip
  "$PIP_VENV" install --quiet -r "$REQ_FILE"
  echo "$REQ_HASH" > "$REQ_HASH_FILE"
else
  echo "$MSG_ALREADY_UP"
fi

# --- Avvio PDFusion ---
echo "$MSG_STARTING"
cd "$SCRIPT_DIR"

# Su Linux imposta DISPLAY se non impostato (headless CI safety)
if [[ "$(uname)" == "Linux" ]] && [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  export DISPLAY=":0"
fi

exec "$PYTHON_VENV" -m src.main "$@"
