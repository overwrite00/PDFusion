import logging
from pathlib import Path

import pikepdf

from core.pdf_opener import open_pdf_safe
from utils.exceptions import PDFusionError
from utils.page_range_parser import parse_page_ranges, ranges_to_indices
from utils.page_validator import validate_page_indices, log_page_operations
from utils.temp_manager import atomic_write

logger = logging.getLogger(__name__)

VALID_ANGLES = {90, 180, 270}


def rotate_pages(
    input_path: Path,
    page_indices: list[int],
    angle: int,
    output_path: Path,
    password: str | None = None,
) -> Path:
    """
    Ruota le pagine indicate di `angle` gradi (90, 180 o 270).

    Args:
        input_path: PDF sorgente.
        page_indices: indici 0-based delle pagine da ruotare.
                      Lista vuota = tutte le pagine.
        angle: 90, 180 o 270 gradi (senso orario).
        output_path: percorso file risultante.
        password: password se il PDF è protetto.

    Returns:
        output_path.

    Raises:
        PDFusionError: Se l'angolo non è valido o gli indici pagina sono fuori range.
    """
    if angle not in VALID_ANGLES:
        raise PDFusionError(f"Angolo non valido: {angle}. Usa 90, 180 o 270.")

    pdf = open_pdf_safe(input_path, password)

    try:
        total = len(pdf.pages)
        targets = page_indices if page_indices else list(range(total))

        # Validate page indices before any PDF modifications
        if page_indices:
            validate_page_indices(page_indices, total)

        for i in targets:
            page = pdf.pages[i]
            current = int(page.get("/Rotate", 0))
            page["/Rotate"] = (current + angle) % 360

        # Log the operation
        log_page_operations(
            "rotate",
            total,
            targets,
            f"angolo {angle}°",
        )

        with atomic_write(output_path) as tmp:
            pdf.save(tmp)
    finally:
        pdf.close()

    return output_path


def rotate_all(
    input_path: Path,
    angle: int,
    output_path: Path,
    password: str | None = None,
) -> Path:
    return rotate_pages(input_path, [], angle, output_path, password)


def rotate_by_range_string(
    input_path: Path,
    range_string: str,
    angle: int,
    output_path: Path,
    password: str | None = None,
) -> Path:
    tmp = open_pdf_safe(input_path, password)
    try:
        total = len(tmp.pages)
    finally:
        tmp.close()

    ranges = parse_page_ranges(range_string, total_pages=total)
    indices = ranges_to_indices(ranges)
    return rotate_pages(input_path, indices, angle, output_path, password)
