from pathlib import Path

import pikepdf

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.page_range_parser import parse_page_ranges, ranges_to_indices
from utils.temp_manager import atomic_write

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
    """
    if angle not in VALID_ANGLES:
        raise PDFusionError(f"Angolo non valido: {angle}. Usa 90, 180 o 270.")

    try:
        kwargs = {"password": password} if password else {}
        pdf = pikepdf.open(input_path, **kwargs)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    try:
        total = len(pdf.pages)
        targets = page_indices if page_indices else list(range(total))

        for i in targets:
            if 0 <= i < total:
                page = pdf.pages[i]
                current = int(page.get("/Rotate", 0))
                page["/Rotate"] = (current + angle) % 360

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
    try:
        kwargs = {"password": password} if password else {}
        tmp = pikepdf.open(input_path, **kwargs)
        total = len(tmp.pages)
        tmp.close()
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    ranges = parse_page_ranges(range_string, total_pages=total)
    indices = ranges_to_indices(ranges)
    return rotate_pages(input_path, indices, angle, output_path, password)
