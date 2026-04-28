import io
from pathlib import Path
from typing import List, Optional, Tuple

import pikepdf
from reportlab.lib.pagesizes import A4, LETTER, A3
from reportlab.pdfgen import canvas

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.page_range_parser import parse_page_ranges, ranges_to_indices
from utils.temp_manager import atomic_write

# Formati pagina disponibili per l'inserimento di pagine bianche
PAGE_SIZES: dict[str, Tuple[float, float]] = {
    "A4": A4,
    "A3": A3,
    "Letter": LETTER,
}


def insert_blank_page(
    input_path: Path,
    position: int,
    output_path: Path,
    page_size: str = "A4",
    password: Optional[str] = None,
) -> Path:
    """
    Inserisce una pagina bianca nel PDF alla posizione indicata.

    Args:
        input_path: PDF sorgente.
        position: posizione 1-based dove inserire la pagina.
                  1 = prima di tutto, None / > total = in fondo.
        output_path: percorso file risultante.
        page_size: "A4", "A3" o "Letter".
        password: password se il PDF è protetto.

    Returns:
        output_path.
    """
    size = PAGE_SIZES.get(page_size, A4)
    blank_bytes = _create_blank_page_bytes(size)
    return _insert_pdf_bytes(input_path, blank_bytes, position, output_path, password)


def insert_from_pdf(
    input_path: Path,
    source_path: Path,
    source_ranges: List[Tuple[int, int]],
    position: int,
    output_path: Path,
    password: Optional[str] = None,
    source_password: Optional[str] = None,
) -> Path:
    """
    Inserisce pagine da un altro PDF alla posizione indicata.

    Args:
        input_path: PDF di destinazione.
        source_path: PDF da cui prendere le pagine.
        source_ranges: range 1-based di pagine da copiare.
        position: posizione 1-based di inserimento nel PDF di destinazione.
        output_path: percorso file risultante.
        password: password del PDF di destinazione.
        source_password: password del PDF sorgente.
    """
    try:
        src_kwargs = {"password": source_password} if source_password else {}
        source_pdf = pikepdf.open(source_path, **src_kwargs)
        src_total = len(source_pdf.pages)
    except pikepdf.PasswordError:
        raise PDFusionError(f"Password errata per '{source_path.name}'.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File sorgente non valido: {source_path.name}") from exc

    try:
        indices = ranges_to_indices(source_ranges) if source_ranges else list(range(src_total))

        # Crea un PDF temporaneo in memoria con solo le pagine selezionate
        buf = io.BytesIO()
        subset = pikepdf.Pdf.new()
        for i in indices:
            if 0 <= i < src_total:
                subset.pages.append(source_pdf.pages[i])
        subset.save(buf)
        buf.seek(0)
        src_bytes = buf.read()
    finally:
        source_pdf.close()

    return _insert_pdf_bytes(input_path, src_bytes, position, output_path, password)


def _insert_pdf_bytes(
    input_path: Path,
    pages_bytes: bytes,
    position: int,
    output_path: Path,
    password: Optional[str],
) -> Path:
    """
    Inserisce le pagine da bytes nel PDF di destinazione alla posizione indicata.
    """
    try:
        dst_kwargs = {"password": password} if password else {}
        dst_pdf = pikepdf.open(input_path, **dst_kwargs)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per il PDF di destinazione.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    try:
        total = len(dst_pdf.pages)
        # Clamp position: 1-based, 1 = inizio, total+1 = fine
        insert_at = max(1, min(position, total + 1)) - 1  # converte a 0-based

        src_pdf = pikepdf.Pdf.open(io.BytesIO(pages_bytes))
        for offset, page in enumerate(src_pdf.pages):
            dst_pdf.pages.insert(insert_at + offset, page)

        with atomic_write(output_path) as tmp:
            dst_pdf.save(tmp)
    finally:
        dst_pdf.close()

    return output_path


def _create_blank_page_bytes(size: Tuple[float, float]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=size)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
