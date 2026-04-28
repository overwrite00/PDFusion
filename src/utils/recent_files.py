import json
from pathlib import Path

from utils.config import MAX_RECENT_FILES, RECENT_FILES_PATH


def _load_raw() -> list[str]:
    try:
        if RECENT_FILES_PATH.exists():
            data = json.loads(RECENT_FILES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_raw(paths: list[str]) -> None:
    try:
        RECENT_FILES_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECENT_FILES_PATH.write_text(
            json.dumps(paths, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def get_recent_files() -> list[Path]:
    """Restituisce la lista dei file recenti che esistono ancora su disco."""
    return [Path(p) for p in _load_raw() if Path(p).exists()]


def add_recent_file(path: Path) -> None:
    """Aggiunge un file in cima alla lista, rimuovendo duplicati."""
    paths = _load_raw()
    s = str(path.resolve())
    if s in paths:
        paths.remove(s)
    paths.insert(0, s)
    _save_raw(paths[:MAX_RECENT_FILES])


def remove_recent_file(path: Path) -> None:
    paths = _load_raw()
    s = str(path.resolve())
    if s in paths:
        paths.remove(s)
        _save_raw(paths)


def clear_recent_files() -> None:
    _save_raw([])
