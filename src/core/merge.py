import logging
import tempfile
from pathlib import Path

import pikepdf

from core.pdf_opener import open_pdf_safe
from utils.exceptions import PDFusionError
from utils.temp_manager import atomic_write

logger = logging.getLogger(__name__)

# Threshold per attivare chunked merge: file > 500 pagine
CHUNKED_MERGE_THRESHOLD = 500

# Dimensione chunk per binary tree merge: 100 pagine per chunk
CHUNK_SIZE = 100


def _merge_simple(
    input_paths: list[Path],
    output_path: Path,
    passwords: list[str | None],
) -> Path:
    """
    Merge semplice sequenziale per PDF piccoli (<500 pagine).
    Carica tutti i PDF in memoria e estende le pagine una volta.

    O(n) memory complexity.
    """
    merged = pikepdf.Pdf.new()

    try:
        opened: list[pikepdf.Pdf] = []

        for path, pwd in zip(input_paths, passwords, strict=False):
            if not path.exists():
                raise PDFusionError(f"File non trovato: {path}")
            pdf = open_pdf_safe(path, pwd)
            opened.append(pdf)
            merged.pages.extend(pdf.pages)

        with atomic_write(output_path) as tmp:
            merged.save(tmp)

    finally:
        for pdf in opened:
            pdf.close()
        merged.close()

    return output_path


def _merge_chunked(
    input_paths: list[Path],
    output_path: Path,
    passwords: list[str | None],
) -> Path:
    """
    Merge chunked per PDF grandi (>500 pagine).
    Implementa binary tree merge per ridurre memory spike.

    Strategia:
    1. Dividi i PDF di input in chunk da CHUNK_SIZE pagine
    2. Fai merge pair-wise dei chunk
    3. Ripeti finché non rimane un solo PDF
    4. Salva il risultato finale

    Memory complexity: O(sqrt(n)) invece di O(n).
    """
    temp_dir = None

    try:
        # Crea directory temporanea per i chunk intermedi
        temp_dir = Path(tempfile.mkdtemp(prefix=".pdfusion_merge_"))
        logger.debug(f"Chunked merge: temp dir = {temp_dir}")

        # Step 1: carica tutti i PDF e crea chunk
        chunks: list[Path] = []
        chunk_counter = 0

        for path, pwd in zip(input_paths, passwords, strict=False):
            if not path.exists():
                raise PDFusionError(f"File non trovato: {path}")

            pdf = open_pdf_safe(path, pwd)
            try:
                total_pages = len(pdf.pages)
                logger.debug(
                    f"File {path.name}: {total_pages} pagine, "
                    f"creando {(total_pages + CHUNK_SIZE - 1) // CHUNK_SIZE} chunk"
                )

                # Dividi in chunk da CHUNK_SIZE pagine
                for chunk_start in range(0, total_pages, CHUNK_SIZE):
                    chunk_end = min(chunk_start + CHUNK_SIZE, total_pages)
                    chunk_pdf = pikepdf.Pdf.new()

                    # Estendi le pagine di questo chunk
                    for page_idx in range(chunk_start, chunk_end):
                        chunk_pdf.pages.append(pdf.pages[page_idx])

                    # Salva il chunk
                    chunk_path = temp_dir / f"chunk_{chunk_counter:06d}.pdf"
                    chunk_pdf.save(str(chunk_path))
                    chunks.append(chunk_path)
                    chunk_counter += 1

                    logger.debug(f"Chunk {chunk_counter - 1}: {chunk_end - chunk_start} pagine")

                    chunk_pdf.close()
            finally:
                pdf.close()

        # Step 2: binary tree merge dei chunk
        # Continua a fondere pair-wise finché non rimane un solo chunk
        while len(chunks) > 1:
            next_chunks: list[Path] = []

            # Fai merge di coppie consecutive
            for i in range(0, len(chunks), 2):
                if i + 1 < len(chunks):
                    # Abbiamo una coppia (i, i+1)
                    left_chunk = chunks[i]
                    right_chunk = chunks[i + 1]

                    merged_chunk = pikepdf.Pdf.new()
                    left_pdf = None
                    right_pdf = None

                    try:
                        left_pdf = pikepdf.open(str(left_chunk))
                        right_pdf = pikepdf.open(str(right_chunk))

                        merged_chunk.pages.extend(left_pdf.pages)
                        merged_chunk.pages.extend(right_pdf.pages)

                        merged_path = temp_dir / f"chunk_{chunk_counter:06d}.pdf"
                        merged_chunk.save(str(merged_path))
                        next_chunks.append(merged_path)
                        chunk_counter += 1

                        logger.debug(
                            f"Merged chunks {i} + {i + 1} → {merged_path.name}, "
                            f"{len(merged_chunk.pages)} pagine"
                        )

                    finally:
                        if left_pdf:
                            left_pdf.close()
                        if right_pdf:
                            right_pdf.close()
                        merged_chunk.close()

                    # Elimina i chunk sorgente (non più servono)
                    try:
                        left_chunk.unlink()
                        right_chunk.unlink()
                    except OSError:
                        pass
                else:
                    # Numero dispari: l'ultimo chunk passa al prossimo livello
                    next_chunks.append(chunks[i])

            chunks = next_chunks

        # Step 3: salva il risultato finale
        assert len(chunks) == 1, "Binary tree merge deve lasciare esattamente 1 chunk"
        final_chunk = chunks[0]

        # Copia il chunk finale all'output finale tramite atomic_write
        final_pdf = pikepdf.open(str(final_chunk))
        try:
            with atomic_write(output_path) as tmp:
                final_pdf.save(str(tmp))
        finally:
            final_pdf.close()

        logger.debug(f"Chunked merge completato: {output_path}")

    finally:
        # Cleanup: elimina temp_dir e tutti i chunk
        if temp_dir and temp_dir.exists():
            try:
                for f in temp_dir.glob("*.pdf"):
                    try:
                        f.unlink()
                    except OSError:
                        pass
                temp_dir.rmdir()
                logger.debug(f"Cleaned up temp dir: {temp_dir}")
            except OSError as e:
                logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")

    return output_path


def merge(
    input_paths: list[Path],
    output_path: Path,
    passwords: list[str | None] | None = None,
) -> Path:
    """
    Unisce più file PDF in uno solo, nell'ordine fornito.
    Sceglie automaticamente tra merge semplice e chunked in base alla dimensione.

    Args:
        input_paths: lista ordinata di PDF da unire (almeno 1).
        output_path: percorso del file risultante.
        passwords: lista di password opzionali, una per ogni file.
                   None o lista vuota = nessun file protetto.

    Returns:
        output_path dopo il salvataggio.

    Raises:
        PDFusionError: se la lista è vuota, un file non esiste, o una
                       password è errata.

    Note:
        - Per PDF con total_pages <= 500: usa _merge_simple (O(n) memory)
        - Per PDF con total_pages > 500: usa _merge_chunked (O(sqrt(n)) memory)
    """
    if len(input_paths) < 1:
        raise PDFusionError("Fornisci almeno un file da unire.")

    if passwords is None:
        passwords = [None] * len(input_paths)
    elif len(passwords) < len(input_paths):
        passwords = list(passwords) + [None] * (len(input_paths) - len(passwords))

    # Valida che tutti i file esistano
    for path in input_paths:
        if not path.exists():
            raise PDFusionError(f"File non trovato: {path}")

    # Calcola total_pages per decidere strategia
    total_pages = 0
    for path, pwd in zip(input_paths, passwords, strict=False):
        pdf = open_pdf_safe(path, pwd)
        try:
            total_pages += len(pdf.pages)
        finally:
            pdf.close()

    logger.info(f"Merge di {len(input_paths)} file, {total_pages} pagine totali")

    # Scegli strategia
    if total_pages <= CHUNKED_MERGE_THRESHOLD:
        logger.debug(f"Usando _merge_simple (total_pages={total_pages})")
        return _merge_simple(input_paths, output_path, passwords)
    else:
        logger.info(
            f"Usando _merge_chunked (total_pages={total_pages} > {CHUNKED_MERGE_THRESHOLD})"
        )
        return _merge_chunked(input_paths, output_path, passwords)


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
        base = open_pdf_safe(base_path, base_password)
        insert = open_pdf_safe(insert_path, insert_password)

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
