from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
from reportlab.pdfgen import canvas as rl_canvas

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.temp_manager import atomic_write

logger = logging.getLogger(__name__)


class WatermarkMode(Enum):
    TEXT = "text"
    IMAGE = "image"


class WatermarkPosition(Enum):
    CENTER_DIAGONAL = "center_diagonal"
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    TILED = "tiled"


class PageSelection(Enum):
    ALL = "all"
    FIRST_ONLY = "first_only"
    LAST_ONLY = "last_only"
    FIRST_AND_LAST = "first_and_last"
    CUSTOM = "custom"


@dataclass
class WatermarkConfig:
    mode: WatermarkMode = WatermarkMode.TEXT
    # Testo
    text: str = "RISERVATO"
    font_size: int = 48
    font_color: tuple[float, float, float] = (0.6, 0.6, 0.6)  # RGB 0-1
    # Immagine
    image_path: Path | None = None
    image_scale: float = 0.5  # 0.1 – 2.0
    # Posizionamento
    position: WatermarkPosition = WatermarkPosition.CENTER_DIAGONAL
    rotation: float = -45.0  # gradi, applicato solo a CENTER_DIAGONAL
    opacity: float = 0.3  # 0.0 – 1.0
    # Applicazione
    page_selection: PageSelection = PageSelection.ALL
    custom_page_indices: list[int] = field(default_factory=list)  # 0-based, per CUSTOM


def apply_watermark(
    input_path: Path,
    output_path: Path,
    config: WatermarkConfig,
    password: str | None = None,
) -> Path:
    """
    Applica il watermark al PDF.

    Strategia:
    - Genera un PDF overlay trasparente con reportlab (testo o immagine)
    - Usa PyMuPDF per stampare l'overlay su ogni pagina target

    Returns:
        output_path.
    """
    if config.mode == WatermarkMode.TEXT and not config.text.strip():
        raise PDFusionError("Il testo del watermark non può essere vuoto.")
    if config.mode == WatermarkMode.IMAGE and (
        config.image_path is None or not config.image_path.exists()
    ):
        raise PDFusionError(f"Immagine watermark non trovata: {config.image_path}")

    try:
        doc = fitz.open(str(input_path))
    except Exception as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    if password and not doc.authenticate(password):
        doc.close()
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    try:
        total = doc.page_count
        target_indices = _resolve_page_indices(config, total)

        for page_idx in target_indices:
            page = doc[page_idx]
            page_rect = page.rect
            overlay_bytes = _generate_overlay(config, page_rect.width, page_rect.height)
            overlay_doc = fitz.open("pdf", overlay_bytes)
            page.show_pdf_page(page_rect, overlay_doc, 0, overlay=True)
            overlay_doc.close()

        with atomic_write(output_path) as tmp:
            doc.save(str(tmp), garbage=1, deflate=True)
    finally:
        doc.close()

    return output_path


def _resolve_page_indices(config: WatermarkConfig, total: int) -> list[int]:
    if config.page_selection == PageSelection.ALL:
        return list(range(total))
    if config.page_selection == PageSelection.FIRST_ONLY:
        return [0] if total > 0 else []
    if config.page_selection == PageSelection.LAST_ONLY:
        return [total - 1] if total > 0 else []
    if config.page_selection == PageSelection.FIRST_AND_LAST:
        if total == 0:
            return []
        if total == 1:
            return [0]
        return [0, total - 1]
    if config.page_selection == PageSelection.CUSTOM:
        return [i for i in config.custom_page_indices if 0 <= i < total]
    return list(range(total))


def _generate_overlay(
    config: WatermarkConfig,
    width: float,
    height: float,
) -> bytes:
    """Genera un PDF overlay trasparente delle dimensioni della pagina."""
    buf = io.BytesIO()
    try:
        c = rl_canvas.Canvas(buf, pagesize=(width, height))
        c.setFillAlpha(config.opacity)
        c.setStrokeAlpha(config.opacity)

        if config.mode == WatermarkMode.TEXT:
            _draw_text_watermark(c, config, width, height)
        else:
            _draw_image_watermark(c, config, width, height)

        c.showPage()
        c.save()
        buf.seek(0)
        return buf.getvalue()
    finally:
        buf.close()


def _draw_text_watermark(
    c: rl_canvas.Canvas,
    config: WatermarkConfig,
    width: float,
    height: float,
) -> None:
    from utils.font_manager import get_font_manager

    r, g, b = config.font_color
    c.setFillColorRGB(r, g, b)

    # Registra il font bundled se disponibile (idempotent tramite FontManager)
    font_manager = get_font_manager()
    font_name = font_manager.register_bundled_font()

    c.setFont(font_name, config.font_size)

    if config.position == WatermarkPosition.CENTER_DIAGONAL:
        c.saveState()
        c.translate(width / 2, height / 2)
        c.rotate(config.rotation)
        c.drawCentredString(0, 0, config.text)
        c.restoreState()

    elif config.position == WatermarkPosition.CENTER:
        c.drawCentredString(width / 2, height / 2, config.text)

    elif config.position == WatermarkPosition.TOP_LEFT:
        c.drawString(20, height - config.font_size - 20, config.text)

    elif config.position == WatermarkPosition.TOP_RIGHT:
        text_width = c.stringWidth(config.text, font_name, config.font_size)
        c.drawString(width - text_width - 20, height - config.font_size - 20, config.text)

    elif config.position == WatermarkPosition.BOTTOM_LEFT:
        c.drawString(20, 20, config.text)

    elif config.position == WatermarkPosition.BOTTOM_RIGHT:
        text_width = c.stringWidth(config.text, font_name, config.font_size)
        c.drawString(width - text_width - 20, 20, config.text)

    elif config.position == WatermarkPosition.TILED:
        text_width = c.stringWidth(config.text, font_name, config.font_size)
        step_x = max(text_width + 40, 100)
        step_y = max(config.font_size + 40, 80)
        c.saveState()
        c.rotate(-30)
        x = -width
        while x < width * 2:
            y = -height
            while y < height * 2:
                c.drawString(x, y, config.text)
                y += step_y
            x += step_x
        c.restoreState()


def _draw_image_watermark(
    c: rl_canvas.Canvas,
    config: WatermarkConfig,
    width: float,
    height: float,
) -> None:
    if not config.image_path or not config.image_path.exists():
        return

    try:
        with Image.open(config.image_path) as img:
            img_w, img_h = img.size

            scale = config.image_scale
            draw_w = img_w * scale
            draw_h = img_h * scale

            if (
                config.position == WatermarkPosition.CENTER_DIAGONAL
                or config.position == WatermarkPosition.CENTER
            ):
                x = (width - draw_w) / 2
                y = (height - draw_h) / 2
            elif config.position == WatermarkPosition.TOP_LEFT:
                x, y = 20, height - draw_h - 20
            elif config.position == WatermarkPosition.TOP_RIGHT:
                x, y = width - draw_w - 20, height - draw_h - 20
            elif config.position == WatermarkPosition.BOTTOM_LEFT:
                x, y = 20, 20
            elif config.position == WatermarkPosition.BOTTOM_RIGHT:
                x, y = width - draw_w - 20, 20
            else:
                x = (width - draw_w) / 2
                y = (height - draw_h) / 2

            c.drawImage(
                str(config.image_path),
                x,
                y,
                width=draw_w,
                height=draw_h,
                mask="auto",
            )
    except Image.UnidentifiedImageError:
        logger.warning(f"Immagine watermark non supportata: {config.image_path}")
    except OSError:
        logger.warning(f"Errore lettura immagine watermark: {config.image_path}")


