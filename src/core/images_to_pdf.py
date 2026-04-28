from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

from utils.exceptions import PDFusionError
from utils.temp_manager import atomic_write

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


class FitMode(Enum):
    FIT_PAGE = "fit_page"       # ridimensiona l'immagine per riempire la pagina
    ORIGINAL_SIZE = "original"  # usa dimensioni originali dell'immagine come pagina
    FIXED_PAGE = "fixed"        # pagina di dimensione fissa (A4 default)


@dataclass
class ImagesToPDFConfig:
    fit_mode: FitMode = FitMode.FIT_PAGE
    fixed_page_size: tuple[float, float] = A4  # usato solo con FIXED_PAGE
    dpi: int = 150              # DPI assunto per le immagini (per ORIGINAL_SIZE)
    jpeg_quality: int = 85      # qualità JPEG per le immagini embedded


def images_to_pdf(
    image_paths: list[Path],
    output_path: Path,
    config: ImagesToPDFConfig | None = None,
) -> Path:
    """
    Crea un PDF da una lista di immagini (una per pagina).

    Args:
        image_paths: lista ordinata di immagini.
        output_path: percorso del PDF risultante.
        config: opzioni di conversione.

    Returns:
        output_path.

    Raises:
        PDFusionError: se la lista è vuota o un file non è supportato.
    """
    if not image_paths:
        raise PDFusionError("Fornisci almeno un'immagine.")

    if config is None:
        config = ImagesToPDFConfig()

    unsupported = [
        p for p in image_paths
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS
    ]
    if unsupported:
        names = ", ".join(p.name for p in unsupported[:5])
        raise PDFusionError(
            f"Formato non supportato: {names}. "
            f"Formati accettati: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    missing = [p for p in image_paths if not p.exists()]
    if missing:
        raise PDFusionError(f"File non trovato: {missing[0]}")

    buf = io.BytesIO()
    c: rl_canvas.Canvas | None = None

    for idx, img_path in enumerate(image_paths):
        try:
            pil_img = Image.open(img_path)
        except Exception as exc:
            raise PDFusionError(f"Impossibile aprire '{img_path.name}': {exc}") from exc

        # Converti in RGB se necessario (RGBA, P, ecc.)
        if pil_img.mode not in ("RGB", "L"):
            pil_img = pil_img.convert("RGB")

        img_w_px, img_h_px = pil_img.size

        page_w, page_h = _compute_page_size(pil_img, config)

        if c is None:
            c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
        else:
            c.setPageSize((page_w, page_h))

        if config.fit_mode == FitMode.FIT_PAGE:
            draw_x, draw_y, draw_w, draw_h = _fit_in_rect(
                img_w_px, img_h_px, page_w, page_h
            )
        elif config.fit_mode == FitMode.ORIGINAL_SIZE:
            pts_per_px = 72.0 / config.dpi
            draw_w = img_w_px * pts_per_px
            draw_h = img_h_px * pts_per_px
            draw_x = (page_w - draw_w) / 2
            draw_y = (page_h - draw_h) / 2
        else:  # FIXED_PAGE
            draw_x, draw_y, draw_w, draw_h = _fit_in_rect(
                img_w_px, img_h_px, page_w, page_h
            )

        # Salva temporaneamente come JPEG in memoria per reportlab
        img_buf = io.BytesIO()
        pil_img.save(img_buf, format="JPEG", quality=config.jpeg_quality)
        img_buf.seek(0)

        c.drawImage(
            img_buf,
            draw_x, draw_y,
            width=draw_w,
            height=draw_h,
        )
        c.showPage()

    if c is None:
        raise PDFusionError("Nessuna immagine valida elaborata.")

    c.save()
    buf.seek(0)

    with atomic_write(output_path) as tmp:
        tmp.write_bytes(buf.read())

    return output_path


def _compute_page_size(
    img: Image.Image,
    config: ImagesToPDFConfig,
) -> tuple[float, float]:
    if config.fit_mode == FitMode.FIXED_PAGE:
        return config.fixed_page_size
    if config.fit_mode == FitMode.FIT_PAGE:
        return A4
    # ORIGINAL_SIZE
    pts_per_px = 72.0 / config.dpi
    return img.size[0] * pts_per_px, img.size[1] * pts_per_px


def _fit_in_rect(
    img_w: int, img_h: int,
    rect_w: float, rect_h: float,
) -> tuple[float, float, float, float]:
    """Calcola posizione e dimensioni per centrare l'immagine nel rettangolo."""
    scale = min(rect_w / img_w, rect_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    draw_x = (rect_w - draw_w) / 2
    draw_y = (rect_h - draw_h) / 2
    return draw_x, draw_y, draw_w, draw_h
