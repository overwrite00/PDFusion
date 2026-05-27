"""
Scrittura atomica di file PDF.

Strategia:
  1. Crea il file temporaneo nella STESSA cartella dell'output
     → os.replace() è sempre sullo stesso filesystem/drive (nessun WinError 17).
  2. Se la cartella non è scrivibile (es. cartella protetta), ricade su
     TEMP_DIR + shutil.move() che gestisce il cross-device copy+delete.
"""

import os
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from utils.config import TEMP_DIR
from utils.exceptions import FileLockedError


def _ensure_dirs() -> None:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_temp() -> None:
    """Rimuove file temporanei orfani (prefisso .pdfusion_) da sessioni precedenti."""
    for search_dir in (TEMP_DIR,):
        if search_dir.exists():
            for f in search_dir.glob(".pdfusion_*.tmp"):
                try:
                    f.unlink()
                except OSError:
                    pass


@contextmanager
def atomic_write(output_path: Path) -> Generator[Path, None, None]:
    """
    Context manager per la scrittura atomica cross-platform.

    Yields un Path temporaneo su cui scrivere. Al termine del blocco,
    sostituisce output_path in modo atomico tramite os.replace().
    Il file temporaneo è creato nella stessa directory dell'output per
    garantire che sorgente e destinazione siano sempre sullo stesso
    filesystem (evita WinError 17 su Windows con drive diversi).

    In caso di errore il file temporaneo viene rimosso e l'originale
    rimane intatto.

    Raises:
        FileLockedError: se output_path è bloccato da un altro processo.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prova a creare il temp nella stessa cartella dell'output (stesso drive)
    try:
        fd, tmp = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=".pdfusion_",
            suffix=".tmp",
        )
    except OSError:
        # Cartella non scrivibile: ricade su TEMP_DIR
        _ensure_dirs()
        fd, tmp = tempfile.mkstemp(dir=TEMP_DIR, prefix=".pdfusion_", suffix=".tmp")

    tmp_path = Path(tmp)
    try:
        os.close(fd)
        yield tmp_path
        # Sostituisce atomicamente — stessa cartella → stesso filesystem
        try:
            os.replace(tmp_path, output_path)
        except PermissionError as exc:
            raise FileLockedError(
                f"Impossibile salvare '{output_path.name}': il file è aperto in un'altra "
                "applicazione. Chiudilo e riprova."
            ) from exc
        except OSError as exc:
            # Fallback cross-device (TEMP_DIR su drive diverso): copia + elimina
            if exc.errno in (17, 18):  # EXDEV / ERROR_NOT_SAME_DEVICE
                try:
                    shutil.copy2(str(tmp_path), str(output_path))
                    tmp_path.unlink(missing_ok=True)
                except PermissionError as pexc:
                    raise FileLockedError(
                        f"Impossibile salvare '{output_path.name}': il file è aperto in "
                        "un'altra applicazione. Chiudilo e riprova."
                    ) from pexc
            else:
                raise
    except BaseException:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
