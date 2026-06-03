import logging
from pathlib import Path

from core.pdf_opener import open_pdf_safe
from core.split import split_ranges
from utils.page_range_parser import parse_page_ranges
from utils.page_validator import validate_page_ranges, log_page_operations

logger = logging.getLogger(__name__)


def extract_pages(
    input_path: Path,
    ranges: list[tuple[int, int]],
    output_path: Path,
    password: str | None = None,
) -> Path:
    """
    Estrae le pagine indicate in un unico nuovo PDF.

    Args:
        input_path: PDF sorgente.
        ranges: range 1-based di pagine da estrarre.
        output_path: percorso del file risultante.
        password: password se il PDF è protetto.

    Returns:
        output_path.

    Raises:
        PDFusionError: Se i range sono invalidi o fuori range.
    """
    # Validate ranges before any PDF operations
    pdf = open_pdf_safe(input_path, password)
    try:
        total = len(pdf.pages)
        validate_page_ranges(ranges, total)
    finally:
        pdf.close()

    # Usa split_ranges con una directory temporanea, poi rinomina il file
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Unifica tutti i range in un singolo range completo
        # estraendo da un file temporaneo intermedio se ci sono più range
        results = split_ranges(
            input_path,
            ranges,
            Path(tmp_dir),
            password,
        )

        # Calculate total extracted pages for logging
        total_extracted = sum(end - start + 1 for start, end in ranges)

        if len(results) == 1:
            import shutil

            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(results[0], output_path)
        else:
            # Più range → unisci in un unico file
            from core.merge import merge

            merge(results, output_path)

        # Log the operation
        log_page_operations(
            "extract",
            total,
            operation_details=f"{total_extracted} pagine estratte in {len(ranges)} range",
        )

    return output_path


def extract_pages_by_range_string(
    input_path: Path,
    range_string: str,
    output_path: Path,
    password: str | None = None,
) -> Path:
    """
    Convenience wrapper: accetta una stringa tipo "1-3, 5, 7-9".
    """
    tmp = open_pdf_safe(input_path, password)
    try:
        total = len(tmp.pages)
    finally:
        tmp.close()

    ranges = parse_page_ranges(range_string, total_pages=total)
    return extract_pages(input_path, ranges, output_path, password)
