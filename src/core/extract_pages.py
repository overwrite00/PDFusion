from pathlib import Path
from typing import List, Optional, Tuple

from core.split import split_ranges
from utils.page_range_parser import parse_page_ranges


def extract_pages(
    input_path: Path,
    ranges: List[Tuple[int, int]],
    output_path: Path,
    password: Optional[str] = None,
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
    """
    # Usa split_ranges con una directory temporanea, poi rinomina il file
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Unifica tutti i range in un singolo range completo
        # estraendo da un file temporaneo intermedio se ci sono più range
        results = split_ranges(
            input_path,
            ranges,
            _Path(tmp_dir),
            password,
        )

        if len(results) == 1:
            import shutil
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(results[0], output_path)
        else:
            # Più range → unisci in un unico file
            from core.merge import merge
            merge(results, output_path)

    return output_path


def extract_pages_by_range_string(
    input_path: Path,
    range_string: str,
    output_path: Path,
    password: Optional[str] = None,
) -> Path:
    """
    Convenience wrapper: accetta una stringa tipo "1-3, 5, 7-9".
    """
    import pikepdf
    from utils.exceptions import PDFusionError

    try:
        kwargs = {"password": password} if password else {}
        tmp = pikepdf.open(input_path, **kwargs)
        total = len(tmp.pages)
        tmp.close()
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")

    ranges = parse_page_ranges(range_string, total_pages=total)
    return extract_pages(input_path, ranges, output_path, password)
