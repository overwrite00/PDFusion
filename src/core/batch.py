from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class BatchOperation(Enum):
    COMPRESS = "compress"
    PROTECT = "protect"
    WATERMARK = "watermark"
    ROTATE = "rotate"
    ADD_HEADERS_FOOTERS = "headers_footers"
    ADD_LICENSE_PAGE = "license_page"
    SPLIT = "split"
    MERGE_TO_ONE = "merge_to_one"  # tutti i file in input → un unico output


@dataclass
class BatchResult:
    input_path: Path
    output_path: Path | None
    success: bool
    error: str | None = None


@dataclass
class BatchJob:
    operation: BatchOperation
    output_dir: Path
    # Config specifica dell'operazione (uno dei dataclass di core/)
    operation_config: Any = None
    # Suffisso aggiunto al nome del file di output (es. "_compressed")
    output_suffix: str = ""
    # Numero di worker paralleli (None = cpu_count)
    max_workers: int | None = None
    # Password comune per tutti i file (None = nessuna)
    password: str | None = None


ProgressCallback = Callable[[int, int, str], None]


def run_batch(
    input_paths: list[Path],
    job: BatchJob,
    progress_callback: ProgressCallback | None = None,
) -> list[BatchResult]:
    """
    Esegue la stessa operazione su tutti i file in input.

    Args:
        input_paths: lista di PDF sorgente.
        job: configurazione dell'operazione batch.
        progress_callback: chiamata con (completati, totale, filename) dopo ogni file.

    Returns:
        Lista di BatchResult, uno per file.
    """

    if not input_paths:
        return []

    job.output_dir.mkdir(parents=True, exist_ok=True)
    total = len(input_paths)
    results: list[BatchResult] = []

    # Operazioni che richiedono tutti i file insieme non si parallelizzano
    if job.operation == BatchOperation.MERGE_TO_ONE:
        output_path = job.output_dir / f"merged{job.output_suffix}.pdf"
        try:
            _run_merge(input_paths, output_path, job)
            results.append(BatchResult(input_paths[0], output_path, True))
        except Exception as exc:
            results.append(BatchResult(input_paths[0], None, False, str(exc)))
        if progress_callback:
            progress_callback(1, 1, output_path.name)
        return results

    completed = 0

    def process_one(path: Path) -> BatchResult:
        out_name = f"{path.stem}{job.output_suffix}.pdf"
        out_path = job.output_dir / out_name
        try:
            _dispatch(path, out_path, job)
            return BatchResult(path, out_path, True)
        except Exception as exc:
            return BatchResult(path, None, False, str(exc))

    workers = min(job.max_workers or 4, total, 8)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(process_one, p): p for p in input_paths}
        for future in concurrent.futures.as_completed(future_map):
            result = future.result()
            results.append(result)
            completed += 1
            if progress_callback:
                progress_callback(completed, total, future_map[future].name)

    # Riordina risultati nell'ordine originale
    order = {p: i for i, p in enumerate(input_paths)}
    results.sort(key=lambda r: order.get(r.input_path, 0))
    return results


def _dispatch(input_path: Path, output_path: Path, job: BatchJob) -> None:
    """Chiama il modulo core corretto in base all'operazione."""
    cfg = job.operation_config
    pwd = job.password

    if job.operation == BatchOperation.COMPRESS:
        from core.compress import compress
        compress(input_path, output_path, cfg, pwd)

    elif job.operation == BatchOperation.PROTECT:
        from core.protect import protect
        protect(input_path, output_path, cfg, pwd)

    elif job.operation == BatchOperation.WATERMARK:
        from core.watermark import apply_watermark
        apply_watermark(input_path, output_path, cfg, pwd)

    elif job.operation == BatchOperation.ROTATE:
        from core.rotate import rotate_all
        angle = cfg if isinstance(cfg, int) else 90
        rotate_all(input_path, angle, output_path, pwd)

    elif job.operation == BatchOperation.ADD_HEADERS_FOOTERS:
        from core.headers_footers import add_headers_footers
        add_headers_footers(input_path, output_path, cfg, password=pwd)

    elif job.operation == BatchOperation.ADD_LICENSE_PAGE:
        from core.license_page import insert_license_page
        insert_license_page(input_path, output_path, cfg, pwd)

    elif job.operation == BatchOperation.SPLIT:
        from core.split import split_every_n
        n = cfg if isinstance(cfg, int) else 1
        split_every_n(input_path, n, output_path.parent, pwd)

    else:
        raise NotImplementedError(f"Operazione non supportata in batch: {job.operation}")


def _run_merge(input_paths: list[Path], output_path: Path, job: BatchJob) -> None:
    from core.merge import merge
    passwords = [job.password] * len(input_paths) if job.password else None
    merge(input_paths, output_path, passwords)
