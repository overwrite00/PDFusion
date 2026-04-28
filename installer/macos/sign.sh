#!/usr/bin/env bash
# Firma il bundle PDFusion.app con un certificato Apple Developer
# Prerequisiti: APPLE_CERTIFICATE (base64) e APPLE_PASSWORD in ambiente
# Uso: bash sign.sh (viene chiamato da GitHub Actions dopo PyInstaller)
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_BUNDLE="$APP_DIR/dist/PDFusion.app"
KEYCHAIN_NAME="pdfusion-build.keychain"
KEYCHAIN_PASSWORD="$(openssl rand -hex 16)"

echo "=== Firma PDFusion.app ==="

if [ ! -d "$APP_BUNDLE" ]; then
  echo "ERRORE: $APP_BUNDLE non trovato."
  exit 1
fi

if [ -z "${APPLE_CERTIFICATE:-}" ]; then
  echo "ATTENZIONE: APPLE_CERTIFICATE non impostato — firma saltata."
  exit 0
fi

# --- Importa certificato in keychain temporanea ---
CERT_FILE="$(mktemp /tmp/pdfusion_cert.XXXXXX.p12)"
echo "$APPLE_CERTIFICATE" | base64 --decode > "$CERT_FILE"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"
security set-keychain-settings -lut 21600 "$KEYCHAIN_NAME"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"
security import "$CERT_FILE" \
  -k "$KEYCHAIN_NAME" \
  -P "${APPLE_PASSWORD:-}" \
  -T /usr/bin/codesign \
  -T /usr/bin/security
security set-key-partition-list \
  -S apple-tool:,apple:,codesign: \
  -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"
security list-keychains -d user -s "$KEYCHAIN_NAME" login.keychain

rm -f "$CERT_FILE"

# Ricava l'identità dal certificato importato
IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN_NAME" \
  | grep -oE '"[^"]+"' | head -1 | tr -d '"')"

echo "Identità: $IDENTITY"

# --- Firma ricorsiva ---
# Prima firma tutte le librerie/framework innestati
find "$APP_BUNDLE" \
  \( -name "*.dylib" -o -name "*.so" -o -name "*.framework" \) \
  -exec codesign --force --sign "$IDENTITY" \
    --options runtime --timestamp {} \;

# Poi firma il bundle principale
codesign --force --sign "$IDENTITY" \
  --options runtime \
  --entitlements "$APP_DIR/installer/macos/entitlements.plist" \
  --timestamp \
  --deep \
  "$APP_BUNDLE"

echo "=== Verifica firma ==="
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"
spctl --assess --type exec --verbose "$APP_BUNDLE" || \
  echo "NOTA: spctl potrebbe fallire senza notarizzazione — normale in CI."

# --- Pulizia keychain ---
security delete-keychain "$KEYCHAIN_NAME"

echo "=== Firma completata ==="
