from __future__ import annotations

import io
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import pikepdf
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from utils.config import BUNDLED_FONT_PATH, LICENSE_TEMPLATES_DIR
from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.temp_manager import atomic_write

# Palette dell'app usata nelle pagine di licenza
_ACCENT = colors.HexColor("#4A6FA5")
_TEXT = colors.HexColor("#1E1E2E")
_TEXT_SEC = colors.HexColor("#6B7280")


class LicenseType(Enum):
    COPYRIGHT = "copyright"
    CC_BY = "cc_by"
    CC_BY_SA = "cc_by_sa"
    CC_BY_NC = "cc_by_nc"
    CC_BY_NC_SA = "cc_by_nc_sa"
    CC_BY_ND = "cc_by_nd"
    CC_BY_NC_ND = "cc_by_nc_nd"
    CC0 = "cc0"
    MIT = "mit"
    PROPRIETARY = "proprietary"
    EDUCATIONAL = "educational"


LICENSE_LABELS = {
    LicenseType.COPYRIGHT: "Copyright — Tutti i diritti riservati",
    LicenseType.CC_BY: "Creative Commons BY 4.0",
    LicenseType.CC_BY_SA: "Creative Commons BY-SA 4.0",
    LicenseType.CC_BY_NC: "Creative Commons BY-NC 4.0",
    LicenseType.CC_BY_NC_SA: "Creative Commons BY-NC-SA 4.0",
    LicenseType.CC_BY_ND: "Creative Commons BY-ND 4.0",
    LicenseType.CC_BY_NC_ND: "Creative Commons BY-NC-ND 4.0",
    LicenseType.CC0: "CC0 1.0 — Pubblico Dominio",
    LicenseType.MIT: "MIT License",
    LicenseType.PROPRIETARY: "Licenza Proprietaria",
    LicenseType.EDUCATIONAL: "Solo Uso Educativo",
}


@dataclass
class LicenseConfig:
    license_type: LicenseType = LicenseType.COPYRIGHT
    author: str = ""
    year: Optional[int] = None
    document_title: Optional[str] = None
    language: str = "it"                        # "it" oppure "en"
    cover_image_path: Optional[Path] = None     # immagine di copertina opzionale


def insert_license_page(
    input_path: Path,
    output_path: Path,
    config: LicenseConfig,
    password: Optional[str] = None,
) -> Path:
    """
    Genera una pagina di licenza e la inserisce in prima posizione nel PDF.

    Returns:
        output_path.
    """
    if not config.author:
        raise PDFusionError("Il nome dell'autore è obbligatorio per la pagina di licenza.")

    license_bytes = _generate_license_page(config)

    # Inserisce in posizione 1 (prima di tutto)
    from core.insert_page import _insert_pdf_bytes
    return _insert_pdf_bytes(input_path, license_bytes, 1, output_path, password)


def _generate_license_page(config: LicenseConfig) -> bytes:
    """Genera un PDF di una pagina con il testo della licenza."""
    import datetime
    year = config.year or datetime.date.today().year
    text = _load_license_text(
        config.license_type, config.author, year, config.document_title, config.language
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=3 * cm,
        rightMargin=3 * cm,
        topMargin=3 * cm,
        bottomMargin=3 * cm,
    )

    _register_fonts()
    styles = _build_styles()
    story = _build_story(text, config, styles, year)

    doc.build(story)
    buf.seek(0)
    return buf.read()


def _load_license_text(
    license_type: LicenseType,
    author: str,
    year: int,
    title: Optional[str],
    language: str = "it",
) -> str:
    """
    Carica il template Jinja2 dalla directory assets.
    Cerca prima la versione nella lingua scelta ({type}_{lang}.txt),
    poi quella in inglese ({type}.txt), infine usa il fallback inline.
    """
    # Candidate templates in ordine di preferenza
    candidates = [
        f"{license_type.value}_{language}.txt",  # es. copyright_it.txt
        f"{license_type.value}.txt",              # es. copyright.txt (inglese)
    ]

    if LICENSE_TEMPLATES_DIR.exists():
        env = Environment(
            loader=FileSystemLoader(str(LICENSE_TEMPLATES_DIR)),
            autoescape=False,
        )
        for template_file in candidates:
            try:
                tmpl = env.get_template(template_file)
                return tmpl.render(author=author, year=year, title=title or "")
            except TemplateNotFound:
                continue

    # Fallback: testo inline minimale
    return _fallback_text(license_type, author, year)


def _fallback_text(license_type: LicenseType, author: str, year: int) -> str:
    label = LICENSE_LABELS.get(license_type, str(license_type.value))
    return (
        f"{label}\n\n"
        f"© {year} {author}\n\n"
        "Questo documento è distribuito secondo i termini della licenza indicata. "
        "Consultare il testo completo della licenza per i termini e le condizioni applicabili."
    )


def _register_fonts() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "PDFusionFont" not in pdfmetrics.getRegisteredFontNames():
        if BUNDLED_FONT_PATH.exists():
            try:
                pdfmetrics.registerFont(TTFont("PDFusionFont", str(BUNDLED_FONT_PATH)))
            except Exception:
                pass


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    font = "PDFusionFont" if _font_registered() else "Helvetica"

    return {
        "title": ParagraphStyle(
            "LicTitle",
            fontName=font,
            fontSize=16,
            textColor=_ACCENT,
            spaceAfter=18,
            leading=20,
        ),
        "body": ParagraphStyle(
            "LicBody",
            fontName=font,
            fontSize=10,
            textColor=_TEXT,
            spaceAfter=8,
            leading=15,
        ),
    }


def _build_story(text: str, config: LicenseConfig, styles: dict, year: int) -> list:
    import io as _io
    from reportlab.platypus import Image as RLImage, PageBreak

    label = LICENSE_LABELS.get(config.license_type, "Licenza")
    story: list = []

    # Immagine di copertina — occupa l'intera area contenuto; il testo va a pag. 2
    if config.cover_image_path and Path(config.cover_image_path).exists():
        try:
            from PIL import Image as PILImage

            # Area contenuto: A4 meno i margini 3 cm per lato (in punti ReportLab)
            max_w = A4[0] - 6 * cm   # ≈ 425 pt  (≈ 15 cm)
            max_h = A4[1] - 6 * cm   # ≈ 672 pt  (≈ 23.7 cm)

            with PILImage.open(str(config.cover_image_path)) as pil_img:
                img_w, img_h = pil_img.size   # pixel originali

                # Scala proporzionale: adatta l'immagine all'area contenuto senza distorsioni
                scale = min(max_w / img_w, max_h / img_h)
                draw_w = img_w * scale   # larghezza di disegno in punti
                draw_h = img_h * scale   # altezza  di disegno in punti

                # Pre-converti in PNG via buffer:
                # evita incompatibilità di ReportLab con BMP, TIFF multi-frame, WebP, ecc.
                converted = (
                    pil_img.convert("RGBA")
                    if pil_img.mode in ("RGBA", "LA", "PA")
                    else pil_img.convert("RGB")
                )
                png_buf = _io.BytesIO()
                converted.save(png_buf, format="PNG", optimize=True)
                png_buf.seek(0)

            img = RLImage(png_buf, width=draw_w, height=draw_h)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(PageBreak())   # il testo della licenza parte sempre dalla pag. 2
        except Exception:
            pass   # immagine non valida: si ignora silenziosamente

    # Testo della licenza (pag. 1 se senza copertina, pag. 2 se con copertina)
    story.append(Paragraph(label, styles["title"]))
    story.append(Spacer(1, 0.3 * cm))

    for paragraph in text.split("\n\n"):
        clean = paragraph.strip().replace("\n", " ")
        if clean:
            story.append(Paragraph(clean, styles["body"]))

    return story


def _font_registered() -> bool:
    from reportlab.pdfbase import pdfmetrics
    return "PDFusionFont" in pdfmetrics.getRegisteredFontNames()
