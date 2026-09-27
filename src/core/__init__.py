"""Core PDF manipulation functions and helpers."""

from pathlib import Path

import pymupdf

from utils.exceptions import PDFusionError


def _open_pdf_with_password(
    path: Path,
    password: str | None = None,
) -> pymupdf.Document:
    """
    Apre un file PDF, gestendo la password se necessaria.

    Args:
        path: Percorso del file PDF.
        password: Password facoltativa se il file è protetto.

    Returns:
        Documento fitz aperto.

    Raises:
        PDFusionError: Se il file non esiste o la password è errata.
    """
    try:
        doc = pymupdf.open(str(path))
    except pymupdf.FileNotFoundError:
        raise PDFusionError(f"File non trovato: {path}")
    except Exception as exc:
        raise PDFusionError(f"Errore apertura PDF: {path}") from exc

    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            doc.close()
            raise PDFusionError("Password errata o mancante per aprire il PDF.")

    return doc
