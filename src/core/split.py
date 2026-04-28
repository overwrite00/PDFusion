from pathlib import Path

import pikepdf

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.page_range_parser import parse_page_ranges
from utils.temp_manager import atomic_write


def split_every_n(
    input_path: Path,
    n: int,
    output_dir: Path,
    password: str | None = None,
) -> list[Path]:
    """
    Divide il PDF in più file di N pagine ciascuno.

    Args:
        input_path: PDF sorgente.
        n: numero di pagine per file di output.
        output_dir: cartella dove salvare i file risultanti.
        password: password se il PDF è protetto.

    Returns:
        Lista ordinata dei file generati.

    Raises:
        PDFusionError: se n < 1 o il PDF non è valido.
    """
    if n < 1:
        raise PDFusionError("Il numero di pagine per file deve essere almeno 1.")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    try:
        pdf = _open_pdf(input_path, password)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    total = len(pdf.pages)
    if total == 0:
        pdf.close()
        raise PDFusionError("Il PDF non contiene pagine.")

    output_paths: list[Path] = []
    chunk_index = 1

    try:
        for start in range(0, total, n):
            end = min(start + n, total)
            out_path = output_dir / f"{stem}_{chunk_index:03d}.pdf"
            with atomic_write(out_path) as tmp:
                subset = pikepdf.Pdf.new()
                subset.pages.extend(pdf.pages[start:end])
                subset.save(tmp)
            output_paths.append(out_path)
            chunk_index += 1
    finally:
        pdf.close()

    return output_paths


def split_ranges(
    input_path: Path,
    ranges: list[tuple[int, int]],
    output_dir: Path,
    password: str | None = None,
) -> list[Path]:
    """
    Divide il PDF secondo range di pagine specificati (1-based).

    Args:
        input_path: PDF sorgente.
        ranges: lista di tuple (start, end) incluse, 1-based.
        output_dir: cartella dove salvare i file risultanti.
        password: password se il PDF è protetto.

    Returns:
        Lista ordinata dei file generati (uno per range).
    """
    if not ranges:
        raise PDFusionError("Nessun range specificato.")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    try:
        pdf = _open_pdf(input_path, password)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    total = len(pdf.pages)
    output_paths: list[Path] = []

    try:
        for i, (start, end) in enumerate(ranges, 1):
            if end > total:
                raise PDFusionError(
                    f"Pagina {end} supera il totale del documento ({total} pagine)."
                )
            out_path = output_dir / f"{stem}_{i:03d}.pdf"
            with atomic_write(out_path) as tmp:
                subset = pikepdf.Pdf.new()
                subset.pages.extend(pdf.pages[start - 1 : end])
                subset.save(tmp)
            output_paths.append(out_path)
    finally:
        pdf.close()

    return output_paths


def split_by_range_string(
    input_path: Path,
    range_string: str,
    output_dir: Path,
    password: str | None = None,
) -> list[Path]:
    """
    Convenience wrapper: accetta una stringa tipo "1-3, 5, 7-9".
    """
    try:
        pdf_tmp = _open_pdf(input_path, password)
        total = len(pdf_tmp.pages)
        pdf_tmp.close()
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    ranges = parse_page_ranges(range_string, total_pages=total)
    return split_ranges(input_path, ranges, output_dir, password)


def _open_pdf(path: Path, password: str | None) -> pikepdf.Pdf:
    try:
        kwargs = {"password": password} if password else {}
        return pikepdf.open(path, **kwargs)
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido o corrotto: {path.name}") from exc
