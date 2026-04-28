#!/usr/bin/env bash
# Crea l'AppImage per PDFusion
# Uso: bash build_appimage.sh v0.1.0
set -euo pipefail

VERSION="${1:-v0.0.0}"
VERSION_CLEAN="${VERSION#v}"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$APP_DIR/dist/PDFusion"
APPDIR="$APP_DIR/installer/linux/AppDir"

echo "=== Build AppImage PDFusion $VERSION_CLEAN ==="

# Pulisci
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copia il bundle PyInstaller
cp -r "$DIST_DIR/." "$APPDIR/usr/bin/"

# .desktop file
cat > "$APPDIR/pdfusion.desktop" << EOF
[Desktop Entry]
Type=Application
Name=PDFusion
Exec=PDFusion
Icon=pdfusion
Categories=Office;PDF;
Comment=Gestione PDF cross-platform
EOF

cp "$APPDIR/pdfusion.desktop" "$APPDIR/usr/share/applications/"

# Icona
cp "$APP_DIR/assets/icons/app.png" "$APPDIR/pdfusion.png"
cp "$APP_DIR/assets/icons/app.png" \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/pdfusion.png"

# AppRun
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF="$(readlink -f "$0")"
HERE="${SELF%/*}"
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/PDFusion" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Crea AppImage
OUTPUT="$APP_DIR/installer/linux/PDFusion-${VERSION_CLEAN}-linux.AppImage"
ARCH=x86_64 appimagetool "$APPDIR" "$OUTPUT"

echo "=== AppImage creata: $OUTPUT ==="
