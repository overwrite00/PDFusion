from pathlib import Path

import pikepdf

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.temp_manager import atomic_write


def merge(
    input_paths: list[Path],
    output_path: Path,
    passwords: list[str | None] | None = None,
) -> Path:
    """
    Unisce più file PDF in uno solo, nell'ordine fornito.

    Args:
        input_paths: lista ordinata di PDF da unire (almeno 2).
        output_path: percorso del file risultante.
        passwords: lista di password opzionali, una per ogni file.
                   None o lista vuota = nessun file protetto.

    Returns:
        output_path dopo il salvataggio.

    Raises:
        PDFusionError: se la lista è vuota, un file non esiste, o una
                       password è errata.
    """
    if len(input_paths) < 1:
        raise PDFusionError("Fornisci almeno un file da unire.")

    if passwords is None:
        passwords = [None] * len(input_paths)
    elif len(passwords) < len(input_paths):
        passwords = list(passwords) + [None] * (len(input_paths) - len(passwords))

    merged = pikepdf.Pdf.new()

    try:
        # Manteniamo i PDF aperti finché il merge non è completato,
        # poi li chiudiamo tutti insieme nel blocco finally.
        opened: list[pikepdf.Pdf] = []

        for path, pwd in zip(input_paths, passwords, strict=False):
            if not path.exists():
                raise PDFusionError(f"File non trovato: {path}")
            try:
                kwargs = {"password": pwd} if pwd else {}
                pdf = pikepdf.open(path, **kwargs)
            except pikepdf.PasswordError:
                raise PDFusionError(f"Password errata o mancante per '{path.name}'.")
            except pikepdf.PdfError as exc:
                raise UnsupportedFormatError(f"File non valido: {path.name}") from exc

            opened.append(pdf)
            merged.pages.extend(pdf.pages)

        with atomic_write(output_path) as tmp:
            merged.save(tmp)

    finally:
        for pdf in opened:
            pdf.close()
        merged.close()

    return output_path


def insert_pdf_at(
    base_path: Path,
    insert_path: Path,
    after_page: int,
    output_path: Path,
    base_password: str | None = None,
    insert_password: str | None = None,
) -> Path:
    """
    Inserisce insert_path all'interno di base_path dopo la pagina indicata.

    after_page è 1-based:
      0                        → prepend (prima di tutto)
      1 … len(base.pages)-1   → inserimento intermedio
      len(base.pages)          → append (in coda, dopo l'ultima pagina)

    Returns:
        output_path dopo il salvataggio.
    """
    if not base_path.exists():
        raise PDFusionError(f"File base non trovato: {base_path}")
    if not insert_path.exists():
        raise PDFusionError(f"File da inserire non trovato: {insert_path}")

    base = insert = result = None
    try:
        try:
            base_kw = {"password": base_password} if base_password else {}
            base = pikepdf.open(base_path, **base_kw)
        except pikepdf.PasswordError:
            raise PDFusionError(f"Password errata o mancante per '{base_path.name}'.")
        except pikepdf.PdfError as exc:
            raise UnsupportedFormatError(f"File base non valido: {base_path.name}") from exc

        try:
            ins_kw = {"password": insert_password} if insert_password else {}
            insert = pikepdf.open(insert_path, **ins_kw)
        except pikepdf.PasswordError:
            raise PDFusionError(f"Password errata o mancante per '{insert_path.name}'.")
        except pikepdf.PdfError as exc:
            raise UnsupportedFormatError(
                f"File da inserire non valido: {insert_path.name}"
            ) from exc

        total = len(base.pages)
        # Blocca after_page nell'intervallo [0, total]
        pos = max(0, min(after_page, total))

        result = pikepdf.Pdf.new()

        # Pagine di base PRIMA del punto di inserimento
        for i in range(pos):
            result.pages.append(base.pages[i])

        # Tutte le pagine del file da inserire
        result.pages.extend(insert.pages)

        # Pagine di base DOPO il punto di inserimento
        for i in range(pos, total):
            result.pages.append(base.pages[i])

        with atomic_write(output_path) as tmp:
            result.save(tmp)

    finally:
        if result:
            result.close()
        if base:
            base.close()
        if insert:
            insert.close()

    return output_path
