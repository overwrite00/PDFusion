import logging
from pathlib import Path

import pikepdf

from core.pdf_opener import open_pdf_safe
from utils.exceptions import PDFusionError
from utils.page_range_parser import parse_page_ranges, ranges_to_indices
from utils.page_validator import validate_page_indices, log_page_operations
from utils.temp_manager import atomic_write

logger = logging.getLogger(__name__)


def delete_pages(
    input_path: Path,
    page_indices: list[int],
    output_path: Path,
    password: str | None = None,
) -> Path:
    """
    Elimina le pagine indicate dal PDF.

    Args:
        input_path: PDF sorgente.
        page_indices: lista di indici 0-based da eliminare.
        output_path: percorso del file risultante.
        password: password se il PDF è protetto.

    Returns:
        output_path dopo il salvataggio.

    Raises:
        PDFusionError: se tutti gli indici sono fuori range o il PDF
                       rimarrebbe senza pagine.
    """
    pdf = open_pdf_safe(input_path, password)

    try:
        total = len(pdf.pages)

        # Validate page indices before any modifications
        if page_indices:
            validate_page_indices(page_indices, total)

        valid = sorted({i for i in page_indices if 0 <= i < total}, reverse=True)

        if not valid:
            raise PDFusionError("Nessuna pagina valida da eliminare.")
        if len(valid) >= total:
            raise PDFusionError(
                "Non è possibile eliminare tutte le pagine: il PDF rimarrebbe vuoto."
            )

        # Store deleted pages before deletion for logging
        deleted_pages = sorted(valid)

        for i in valid:
            del pdf.pages[i]

        # Log the operation
        log_page_operations(
            "delete",
            total,
            deleted_pages,
            f"{len(deleted_pages)} pagine eliminate",
        )

        with atomic_write(output_path) as tmp:
            pdf.save(tmp)
    finally:
        pdf.close()

    return output_path


def delete_page_by_number(
    input_path: Path,
    page_number: int,
    output_path: Path,
    password: str | None = None,
) -> Path:
    """
    Elimina una singola pagina (1-based).
    """
    return delete_pages(input_path, [page_number - 1], output_path, password)


def delete_pages_by_range_string(
    input_path: Path,
    range_string: str,
    output_path: Path,
    password: str | None = None,
) -> Path:
    """
    Elimina pagine indicate da stringa tipo "1-3, 5".
    """
    tmp_pdf = open_pdf_safe(input_path, password)
    try:
        total = len(tmp_pdf.pages)
    finally:
        tmp_pdf.close()

    ranges = parse_page_ranges(range_string, total_pages=total)
    indices = ranges_to_indices(ranges)
    return delete_pages(input_path, indices, output_path, password)
