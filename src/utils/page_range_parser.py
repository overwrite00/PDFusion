import re

from utils.exceptions import InvalidPageRangeError

# Corrisponde sia a "-" ASCII che a "–" en-dash
_RANGE_SEP = r"[-–]"


def parse_page_ranges(
    text: str,
    total_pages: int | None = None,
) -> list[tuple[int, int]]:
    """
    Converte una stringa come "1-3, 5, 7-9" in [(1,3), (5,5), (7,9)].

    Le pagine sono 1-based. Accetta separatori virgola e punto-e-virgola,
    spazi arbitrari, e sia "-" che "–" come separatore di range.

    Args:
        text: stringa di input dell'utente.
        total_pages: se fornito, controlla che nessuna pagina superi il totale.

    Returns:
        Lista di tuple (start, end) incluse, 1-based.

    Raises:
        InvalidPageRangeError: se la stringa è invalida o fuori range.
    """
    text = text.strip()
    if not text:
        raise InvalidPageRangeError("Inserisci almeno un numero di pagina.")

    parts = re.split(r"[,;]", text)
    ranges: list[tuple[int, int]] = []

    for raw in parts:
        part = raw.strip()
        if not part:
            continue

        # Range "3-7" o "3–7"
        m = re.fullmatch(rf"(\d+)\s*{_RANGE_SEP}\s*(\d+)", part)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            _validate_range(start, end, total_pages)
            ranges.append((start, end))
            continue

        # Pagina singola "5"
        m = re.fullmatch(r"(\d+)", part)
        if m:
            page = int(m.group(1))
            _validate_range(page, page, total_pages)
            ranges.append((page, page))
            continue

        raise InvalidPageRangeError(
            f"Formato non riconosciuto: '{part}'. Usa es. '1-3, 5, 7-9'."
        )

    if not ranges:
        raise InvalidPageRangeError("Nessun range valido trovato.")

    return ranges


def _validate_range(start: int, end: int, total_pages: int | None) -> None:
    if start < 1:
        raise InvalidPageRangeError(
            f"Numero pagina non valido: {start}. Le pagine partono da 1."
        )
    if end < start:
        raise InvalidPageRangeError(
            f"Range non valido: {start}-{end}. Il numero finale deve essere ≥ quello iniziale."
        )
    if total_pages is not None and end > total_pages:
        raise InvalidPageRangeError(
            f"Pagina {end} supera il totale del documento ({total_pages} pagine)."
        )


def ranges_to_indices(ranges: list[tuple[int, int]]) -> list[int]:
    """Converte range 1-based in lista ordinata di indici 0-based univoci."""
    indices: set[int] = set()
    for start, end in ranges:
        for i in range(start - 1, end):
            indices.add(i)
    return sorted(indices)


def format_page_ranges(ranges: list[tuple[int, int]]) -> str:
    """Converte [(1,3),(5,5),(7,9)] in '1-3, 5, 7-9'."""
    parts = []
    for start, end in ranges:
        parts.append(str(start) if start == end else f"{start}-{end}")
    return ", ".join(parts)
