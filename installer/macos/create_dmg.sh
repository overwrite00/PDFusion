#!/usr/bin/env bash
# Crea il file .dmg per PDFusion su macOS
# Uso: bash create_dmg.sh v0.1.0
set -euo pipefail

VERSION="${1:-v0.0.0}"
VERSION_CLEAN="${VERSION#v}"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_BUNDLE="$APP_DIR/dist/PDFusion.app"
OUTPUT="$APP_DIR/installer/macos/PDFusion-${VERSION_CLEAN}-macos.dmg"

echo "=== Build DMG PDFusion $VERSION_CLEAN ==="

if [ ! -d "$APP_BUNDLE" ]; then
  echo "ERRORE: $APP_BUNDLE non trovato. Esegui prima PyInstaller."
  exit 1
fi

create-dmg \
  --volname "PDFusion $VERSION_CLEAN" \
  --volicon "$APP_DIR/assets/icons/app.icns" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "PDFusion.app" 175 190 \
  --hide-extension "PDFusion.app" \
  --app-drop-link 425 190 \
  --no-internet-enable \
  "$OUTPUT" \
  "$APP_BUNDLE"

echo "=== DMG creato: $OUTPUT ==="
