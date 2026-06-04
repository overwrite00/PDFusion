from pathlib import Path

APP_NAME = "PDFusion"
VERSION = "0.2.1"

# Percorsi strutturali
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
