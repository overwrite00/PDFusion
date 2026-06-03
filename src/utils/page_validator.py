"""Page range validation utility for PDF operations."""
import logging

from utils.exceptions import PDFusionError

logger = logging.getLogger(__name__)


def validate_page_index(page_idx: int, total_pages: int) -> None:
    """
    Validate a single page index (0-based).

    Args:
        page_idx: The page index to validate (0-based).
        total_pages: Total number of pages in the PDF.

    Raises:
        PDFusionError: If the page index is out of bounds.
    """
    if not isinstance(page_idx, int):
        raise PDFusionError(f"Indice pagina non valido: {page_idx}. Deve essere un numero intero.")

    # Support Python-style negative indices
    if page_idx < 0:
        # Convert negative index to positive
        positive_idx = total_pages + page_idx
        if positive_idx < 0:
            raise PDFusionError(
                f"Indice pagina {page_idx} non valido. "
                f"Il PDF ha {total_pages} pagine (valido: -{total_pages} a {total_pages - 1})."
            )
        return

    if page_idx >= total_pages:
        closest = total_pages - 1 if total_pages > 0 else -1
        suggestion = f" Intendevi pagina {closest}?" if closest >= 0 else ""
        raise PDFusionError(
            f"Pagina {page_idx + 1} non esiste. Il PDF ha {total_pages} pagine.{suggestion}"
        )


def validate_page_indices(page_indices: list[int], total_pages: int) -> None:
    """
    Validate a list of page indices (0-based).

    Args:
        page_indices: List of page indices to validate (0-based).
        total_pages: Total number of pages in the PDF.

    Raises:
        PDFusionError: If any page index is out of bounds or list is empty.
    """
    if not page_indices:
        raise PDFusionError("La lista di indici pagina è vuota.")

    for idx in page_indices:
        validate_page_index(idx, total_pages)


def validate_page_range(start: int, end: int, total_pages: int) -> None:
    """
    Validate a page range (1-based, inclusive).

    Args:
        start: Start page number (1-based, inclusive).
        end: End page number (1-based, inclusive).
        total_pages: Total number of pages in the PDF.

    Raises:
        PDFusionError: If the range is invalid.
    """
    if start < 1:
        raise PDFusionError(f"Numero pagina inizio non valido: {start}. Le pagine partono da 1.")

    if end < start:
        raise PDFusionError(
            f"Range non valido: {start}-{end}. Il numero finale deve essere >= quello iniziale."
        )

    if end > total_pages:
        suggestion = f" Intendevi fino alla pagina {total_pages}?" if total_pages > 0 else ""
        raise PDFusionError(
            f"Pagina {end} supera il totale del documento ({total_pages} pagine).{suggestion}"
        )


def validate_page_ranges(
    ranges: list[tuple[int, int]],
    total_pages: int,
) -> None:
    """
    Validate a list of page ranges (1-based, inclusive).

    Args:
        ranges: List of (start, end) tuples (1-based, inclusive).
        total_pages: Total number of pages in the PDF.

    Raises:
        PDFusionError: If any range is invalid.
    """
    if not ranges:
        raise PDFusionError("La lista di range pagine è vuota.")

    for start, end in ranges:
        validate_page_range(start, end, total_pages)


def log_page_operations(
    operation: str,
    total_pages: int,
    affected_pages: list[int] | set[int] | None = None,
    operation_details: str | None = None,
) -> None:
    """
    Log page operations with relevant details.

    Args:
        operation: Name of the operation (e.g., "rotate", "delete", "extract").
        total_pages: Total number of pages in the PDF.
        affected_pages: List/set of affected page indices (0-based) or page numbers (1-based).
        operation_details: Additional details about the operation.
    """
    if affected_pages:
        page_list = sorted(affected_pages)
        page_count = len(page_list)
        pages_str = (
            f"pagine {page_list[0] + 1}-{page_list[-1] + 1}"
            if page_count > 1 and page_list[-1] - page_list[0] + 1 == page_count
            else f"pagine: {', '.join(str(p + 1) for p in page_list[:10])}"
            + ("..." if page_count > 10 else "")
        )
        detail = f" ({pages_str})" if pages_str else ""
    else:
        detail = ""

    msg = f"Operazione '{operation}' su PDF con {total_pages} pagine{detail}"
    if operation_details:
        msg += f" - {operation_details}"

    logger.info(msg)
