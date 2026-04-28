from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.page_range_parser import parse_page_ranges, ranges_to_indices


class ImageFormat(Enum):
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"


@dataclass
class ExportImagesConfig:
    format: ImageFormat = ImageFormat.PNG
    dpi: int = 150
    page_range: Optional[str] = None  # None = tutte le pagine
    jpeg_quality: int = 85            # usato solo per JPEG


def export_pages_as_images(
    input_path: Path,
    output_dir: Path,
    config: Optional[ExportImagesConfig] = None,
    password: Optional[str] = None,
) -> List[Path]:
    """
    Esporta le pagine del PDF come immagini.

    Args:
        input_path: PDF sorgente.
        output_dir: cartella di output (creata se non esiste).
        config: opzioni di esportazione.
        password: password se il PDF è protetto.

    Returns:
        Lista ordinata dei file immagine generati.
    """
    if config is None:
        config = ExportImagesConfig()

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    try:
        doc = fitz.open(str(input_path))
    except Exception as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    if password and not doc.authenticate(password):
        doc.close()
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    try:
        total = doc.page_count
        indices = _resolve_indices(config.page_range, total)

        ext = config.format.value
        zoom = config.dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        output_paths: List[Path] = []
        for page_idx in indices:
            page = doc[page_idx]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)

            out_path = output_dir / f"{stem}_page_{page_idx + 1:04d}.{ext}"

            if config.format == ImageFormat.JPEG:
                pixmap.save(str(out_path), jpg_quality=config.jpeg_quality)
            else:
                pixmap.save(str(out_path))

            output_paths.append(out_path)
    finally:
        doc.close()

    return output_paths


def _resolve_indices(page_range: Optional[str], total: int) -> List[int]:
    if not page_range:
        return list(range(total))
    try:
        ranges = parse_page_ranges(page_range, total_pages=total)
        return ranges_to_indices(ranges)
    except Exception:
        return list(range(total))
