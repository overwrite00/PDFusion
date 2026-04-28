from pathlib import Path
from typing import List, Optional

import pikepdf

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.page_range_parser import parse_page_ranges, ranges_to_indices
from utils.temp_manager import atomic_write


def delete_pages(
    input_path: Path,
    page_indices: List[int],
    output_path: Path,
    password: Optional[str] = None,
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
    try:
        kwargs = {"password": password} if password else {}
        pdf = pikepdf.open(input_path, **kwargs)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    try:
        total = len(pdf.pages)
        valid = sorted({i for i in page_indices if 0 <= i < total}, reverse=True)

        if not valid:
            raise PDFusionError("Nessuna pagina valida da eliminare.")
        if len(valid) >= total:
            raise PDFusionError(
                "Non è possibile eliminare tutte le pagine: il PDF rimarrebbe vuoto."
            )

        for i in valid:
            del pdf.pages[i]

        with atomic_write(output_path) as tmp:
            pdf.save(tmp)
    finally:
        pdf.close()

    return output_path


def delete_page_by_number(
    input_path: Path,
    page_number: int,
    output_path: Path,
    password: Optional[str] = None,
) -> Path:
    """
    Elimina una singola pagina (1-based).
    """
    return delete_pages(input_path, [page_number - 1], output_path, password)


def delete_pages_by_range_string(
    input_path: Path,
    range_string: str,
    output_path: Path,
    password: Optional[str] = None,
) -> Path:
    """
    Elimina pagine indicate da stringa tipo "1-3, 5".
    """
    try:
        kwargs = {"password": password} if password else {}
        tmp_pdf = pikepdf.open(input_path, **kwargs)
        total = len(tmp_pdf.pages)
        tmp_pdf.close()
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    ranges = parse_page_ranges(range_string, total_pages=total)
    indices = ranges_to_indices(ranges)
    return delete_pages(input_path, indices, output_path, password)
