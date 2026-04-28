from __future__ import annotations

import datetime
import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as rl_canvas

from utils.config import BUNDLED_FONT_PATH
from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.page_range_parser import parse_page_ranges, ranges_to_indices
from utils.temp_manager import atomic_write

# Variabili supportate nel testo: {page}, {total}, {date}, {title}, {author}
_DEFAULT_DATE = datetime.date.today().strftime("%d/%m/%Y")

_TEXT_COLOR = HexColor("#1E1E2E")
_TEXT_SEC_COLOR = HexColor("#6B7280")


@dataclass
class HeaderFooterSection:
    """Contenuto di una singola sezione (sinistra, centro, destra)."""
    left: str = ""
    center: str = ""
    right: str = ""


@dataclass
class HeaderFooterConfig:
    header: HeaderFooterSection = field(default_factory=HeaderFooterSection)
    footer: HeaderFooterSection = field(default_factory=HeaderFooterSection)
    font_size: int = 9
    font_color: str = "#6B7280"
    # Margine dai bordi della pagina (in punti PDF)
    margin_horizontal: float = 36.0   # ~1.27 cm
    margin_vertical: float = 28.0     # ~1.00 cm  (Word default: ~1.27 cm)
    # Range di pagine su cui applicare (None = tutte)
    page_range: str | None = None
    # Differenziazione prima pagina e pagine pari/dispari
    different_first_page: bool = False
    different_odd_even: bool = False
    first_page_header: HeaderFooterSection = field(default_factory=HeaderFooterSection)
    first_page_footer: HeaderFooterSection = field(default_factory=HeaderFooterSection)
    even_header: HeaderFooterSection = field(default_factory=HeaderFooterSection)
    even_footer: HeaderFooterSection = field(default_factory=HeaderFooterSection)


def add_headers_footers(
    input_path: Path,
    output_path: Path,
    config: HeaderFooterConfig,
    document_title: str | None = None,
    document_author: str | None = None,
    password: str | None = None,
) -> Path:
    """
    Aggiunge intestazioni e/o piè di pagina al PDF.

    Le variabili supportate nel testo sono:
        {page}   → numero pagina corrente (1-based)
        {total}  → numero totale di pagine
        {date}   → data odierna (gg/mm/aaaa)
        {title}  → titolo del documento (da metadati o param)
        {author} → autore (da metadati o param)

    Returns:
        output_path.
    """
    if not _has_content(config):
        # Nessun testo specificato: copia il documento senza modifiche.
        # Questo consente di "annullare" visivamente un'anteprima precedente
        # tornando al documento corrente senza applicare nulla.
        with atomic_write(output_path) as tmp:
            shutil.copy2(str(input_path), str(tmp))
        return output_path

    try:
        doc = fitz.open(str(input_path))
    except Exception as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    if password and not doc.authenticate(password):
        doc.close()
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    try:
        total = doc.page_count

        # Leggi metadati per le variabili {title} e {author}
        meta = doc.metadata
        title = document_title or meta.get("title", "")
        author = document_author or meta.get("author", "")

        # Calcola gli indici target
        target_indices = _resolve_indices(config.page_range, total)

        for page_idx in target_indices:
            page_num = page_idx + 1  # 1-based

            # Seleziona le sezioni appropriate per questa pagina
            if config.different_first_page and page_num == 1:
                use_header = config.first_page_header
                use_footer = config.first_page_footer
            elif config.different_odd_even and page_num % 2 == 0:
                use_header = config.even_header
                use_footer = config.even_footer
            else:
                use_header = config.header
                use_footer = config.footer

            # Salta se non c'è contenuto per questa pagina
            if not _section_has_content(use_header) and not _section_has_content(use_footer):
                continue

            page = doc[page_idx]
            page_rect = page.rect

            vars_ = {
                "page": str(page_num),
                "total": str(total),
                "date": _DEFAULT_DATE,
                "title": title,
                "author": author,
            }

            overlay_bytes = _generate_overlay(
                config, use_header, use_footer, vars_, page_rect.width, page_rect.height
            )
            overlay_doc = fitz.open("pdf", overlay_bytes)
            page.show_pdf_page(page_rect, overlay_doc, 0, overlay=True)
            overlay_doc.close()

        with atomic_write(output_path) as tmp:
            doc.save(str(tmp), garbage=1, deflate=True)
    finally:
        doc.close()

    return output_path


def _generate_overlay(
    config: HeaderFooterConfig,
    header: HeaderFooterSection,
    footer: HeaderFooterSection,
    vars_: dict,
    width: float,
    height: float,
) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width, height))

    font_name = _get_font()
    c.setFont(font_name, config.font_size)

    try:
        col = HexColor(config.font_color)
        c.setFillColor(col)
    except Exception:
        c.setFillColorRGB(0.42, 0.45, 0.50)

    mx = config.margin_horizontal
    my = config.margin_vertical

    # Header
    if _section_has_content(header):
        y_header = height - my
        _draw_section(c, header, vars_, mx, y_header, width, config.font_size)

    # Footer
    if _section_has_content(footer):
        y_footer = my
        _draw_section(c, footer, vars_, mx, y_footer, width, config.font_size)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _draw_section(
    c: rl_canvas.Canvas,
    section: HeaderFooterSection,
    vars_: dict,
    mx: float,
    y: float,
    page_width: float,
    font_size: int,
) -> None:
    font_name = _get_font()

    if section.left:
        text = _substitute(section.left, vars_)
        c.drawString(mx, y, text)

    if section.center:
        text = _substitute(section.center, vars_)
        text_width = c.stringWidth(text, font_name, font_size)
        c.drawString((page_width - text_width) / 2, y, text)

    if section.right:
        text = _substitute(section.right, vars_)
        text_width = c.stringWidth(text, font_name, font_size)
        c.drawString(page_width - mx - text_width, y, text)


def _substitute(template: str, vars_: dict) -> str:
    try:
        return template.format(**vars_)
    except (KeyError, ValueError):
        return template


def _resolve_indices(page_range: str | None, total: int) -> list[int]:
    if not page_range:
        return list(range(total))
    try:
        ranges = parse_page_ranges(page_range, total_pages=total)
        return ranges_to_indices(ranges)
    except Exception:
        return list(range(total))


def _has_content(config: HeaderFooterConfig) -> bool:
    if _section_has_content(config.header) or _section_has_content(config.footer):
        return True
    if config.different_first_page and (
        _section_has_content(config.first_page_header)
        or _section_has_content(config.first_page_footer)
    ):
        return True
    if config.different_odd_even and (
        _section_has_content(config.even_header)
        or _section_has_content(config.even_footer)
    ):
        return True
    return False


def _section_has_content(section: HeaderFooterSection) -> bool:
    return bool(section.left or section.center or section.right)


def _get_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    name = "PDFusionFont"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    if BUNDLED_FONT_PATH.exists():
        try:
            pdfmetrics.registerFont(TTFont(name, str(BUNDLED_FONT_PATH)))
            return name
        except Exception:
            pass
    return "Helvetica"
