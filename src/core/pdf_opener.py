"""
PDF Opener Helper Module - DRY principle implementation.

Fornisce un'interfaccia unificata e sicura per l'apertura di file PDF
con gestione centralizzata degli errori e support per password.
"""

import logging
from pathlib import Path

import pikepdf

from utils.exceptions import PDFusionError, UnsupportedFormatError

logger = logging.getLogger(__name__)


def open_pdf_safe(
    path: Path,
    password: str | None = None,
    mode: str = "r",
) -> pikepdf.Pdf:
    """
    Apre un file PDF con gestione centralizzata degli errori.

    Questa funzione implementa il DRY principle consolidando la logica
    comune di apertura PDF da 9+ file nel codebase.

    Args:
        path: Percorso del file PDF.
        password: Password opzionale per PDF protetti. Se None, nessuna
                  password viene utilizzata.
        mode: Modalità di apertura ("r", "w", "a"). Default: "r" (lettura).

    Returns:
        pikepdf.Pdf: Oggetto PDF aperto e pronto per l'uso.

    Raises:
        PDFusionError: Se il file non esiste o la password è errata.
        UnsupportedFormatError: Se il file non è un PDF valido o è corrotto.

    Examples:
        >>> pdf = open_pdf_safe(Path("document.pdf"))
        >>> pdf.close()

        >>> pdf = open_pdf_safe(Path("protected.pdf"), password="secret")
        >>> pdf.close()
    """
    logger.debug(f"Opening PDF: {path.name} (mode={mode}, password={'***' if password else 'None'})")

    # Validazione percorso
    if not path.exists():
        logger.error(f"File not found: {path}")
        raise PDFusionError(f"File non trovato: {path}")

    try:
        # Costruisci kwargs in modo sicuro
        kwargs = {}
        if password:
            kwargs["password"] = password
        if mode != "r":
            kwargs["allow_overwriting_input"] = False

        # Tentativo apertura
        pdf = pikepdf.open(path, **kwargs)
        logger.debug(f"Successfully opened PDF: {path.name}")
        return pdf

    except pikepdf.PasswordError as exc:
        logger.error(f"Password error for {path.name}: {exc}")
        raise PDFusionError(
            f"Password errata o mancante per aprire il PDF."
        ) from exc

    except pikepdf.PdfError as exc:
        logger.error(f"PDF error for {path.name}: {exc}")
        raise UnsupportedFormatError(
            f"File non valido o corrotto: {path.name}"
        ) from exc

    except (OSError, IOError) as exc:
        logger.error(f"IO error for {path.name}: {exc}")
        raise PDFusionError(
            f"Errore di accesso al file: {path.name}"
        ) from exc

    except Exception as exc:
        logger.error(f"Unexpected error opening {path.name}: {exc}")
        raise UnsupportedFormatError(
            f"Errore inaspettato durante apertura PDF: {path.name}"
        ) from exc
