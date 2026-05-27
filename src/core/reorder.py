from pathlib import Path

import pikepdf

from core.pdf_opener import open_pdf_safe
from utils.exceptions import PDFusionError
from utils.temp_manager import atomic_write


def reorder_pages(
    input_path: Path,
    new_order: list[int],
    output_path: Path,
    password: str | None = None,
) -> Path:
    """
    Riordina le pagine del PDF secondo la nuova sequenza indicata.

    Args:
        input_path: PDF sorgente.
        new_order: lista di indici 0-based nel nuovo ordine desiderato.
                   Deve contenere esattamente tutti gli indici validi
                   (nessuna duplicazione, nessuna omissione).
        output_path: percorso file risultante.
        password: password se il PDF è protetto.

    Returns:
        output_path.

    Raises:
        PDFusionError: se new_order non è una permutazione valida degli indici.
    """
    pdf = open_pdf_safe(input_path, password)

    try:
        total = len(pdf.pages)
        _validate_order(new_order, total)

        reordered = pikepdf.Pdf.new()
        for i in new_order:
            reordered.pages.append(pdf.pages[i])

        with atomic_write(output_path) as tmp:
            reordered.save(tmp)
    finally:
        pdf.close()

    return output_path


def _validate_order(new_order: list[int], total: int) -> None:
    if len(new_order) != total:
        raise PDFusionError(
            f"Il nuovo ordine deve contenere esattamente {total} elementi "
            f"(ricevuti {len(new_order)})."
        )
    if sorted(new_order) != list(range(total)):
        raise PDFusionError(
            "Il nuovo ordine deve essere una permutazione degli indici originali "
            f"(0 – {total - 1}), senza duplicati né omissioni."
        )
