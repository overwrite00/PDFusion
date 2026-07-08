import sys
from pathlib import Path

APP_NAME = "PDFusion"
VERSION = "0.2.8"

# Percorsi strutturali
#
# In modalità "dev" (python src/main.py) __file__ punta dentro il repo e
# .parent.parent.parent risale correttamente fino alla root del progetto.
#
# In build PyInstaller (frozen), src/utils/config.py NON esiste più come
# file su disco: il modulo viene caricato dall'archivio PYZ e __file__ è un
# path sintetico (<MEIPASS>/utils/config.py — nota: senza il prefisso
# "src/", perché pathex=[SRC_DIR] nello spec appiattisce i pacchetti top
# level). Risalire di 3 parent da lì porta un livello SOPRA sys._MEIPASS
# (che per build onedir è la cartella "_internal"), mentre gli asset
# vengono realmente copiati da PDFusion.spec dentro
# "_internal/assets/...". Il vecchio calcolo puntava quindi a una cartella
# "assets" inesistente accanto all'exe: QIcon/Jinja2 fallivano in silenzio
# (icona vuota/quadrato bianco, template licenze non trovati) solo nelle
# build compilate, mai in dev — per questo il bug è rimasto invisibile.
if getattr(sys, "frozen", False):
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]
    APP_DIR = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    APP_DIR = Path(__file__).resolve().parent.parent.parent
    ASSETS_DIR = APP_DIR / "assets"
LICENSE_TEMPLATES_DIR = ASSETS_DIR / "licenses" / "templates"
FONTS_DIR = ASSETS_DIR / "fonts"
ICONS_DIR = ASSETS_DIR / "icons"

# Percorsi runtime (nella home utente)
PDFUSION_DIR = Path.home() / ".pdfusion"
RECENT_FILES_PATH = PDFUSION_DIR / "recent.json"
TEMP_DIR = PDFUSION_DIR / "tmp"

# Limiti
MAX_RECENT_FILES = 10
MAX_BATCH_FILES = 500

# Preset testo watermark (italiano, inglese)
WATERMARK_PRESETS_IT = [
    "RISERVATO",
    "BOZZA",
    "COPIA",
    "APPROVATO",
    "CAMPIONE",
    "ANNULLATO",
    "CONFIDENZIALE",
    "IN REVISIONE",
    "ARCHIVIO",
    "NON UFFICIALE",
    "PROPRIETÀ RISERVATA",
]

WATERMARK_PRESETS_EN = [
    "CONFIDENTIAL",
    "DRAFT",
    "COPY",
    "APPROVED",
    "SAMPLE",
    "CANCELLED",
    "RESTRICTED",
    "UNDER REVIEW",
    "ARCHIVE",
    "UNOFFICIAL",
    "PROPRIETARY",
]

# Font bundled (usato da reportlab per watermark, licenze, intestazioni)
BUNDLED_FONT_PATH = FONTS_DIR / "NotoSans-Regular.ttf"
BUNDLED_FONT_BOLD_PATH = FONTS_DIR / "NotoSans-Bold.ttf"
