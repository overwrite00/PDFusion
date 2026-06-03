from __future__ import annotations

import concurrent.futures
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
    # Usato come fallback se password_map non contiene il file
    password: str | None = None
    # Mappa per-file: Path -> password
    # Se presente, ha precedenza su job.password
    password_map: dict[Path, str | None] | None = None
    # Timeout per file singolo in secondi (default: 30)
    timeout: float = 30.0
    # Numero massimo di tentativi per file (default: 1 = no retry)
    max_retries: int = 1


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
    processed_paths = set()  # Track which paths already have results

    def process_one(path: Path) -> BatchResult:
        out_name = f"{path.stem}{job.output_suffix}.pdf"
        out_path = job.output_dir / out_name
        try:
            _dispatch(path, out_path, job)
            return BatchResult(path, out_path, True)
        except Exception as exc:
            return BatchResult(path, None, False, str(exc))

    workers = min(job.max_workers or 4, total, 8)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(process_one, p): p for p in input_paths}
            retry_queue = {}  # {path: retry_count}

            try:
                for future in concurrent.futures.as_completed(
                    future_map, timeout=job.timeout
                ):
                    path = future_map[future]
                    result = future.result()
                    results.append(result)
                    processed_paths.add(path)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total, path.name)
            except concurrent.futures.TimeoutError:
                # Handle timeout: cancel pending futures and process results
                remaining = total - len(results)
                logger.warning(
                    "Batch timeout: %d/%d jobs exceeded %f seconds",
                    remaining,
                    total,
                    job.timeout,
                )

                # Collect all unprocessed paths and mark as timeout
                timeout_errors = {}
                for future, path in future_map.items():
                    if path in processed_paths:
                        # Already processed successfully
                        continue

                    if not future.done():
                        # Future is still pending, cancel and mark as timeout
                        future.cancel()
                        error_msg = (
                            f"Timeout: file processing exceeded {job.timeout} seconds"
                        )
                        timeout_errors[path] = error_msg
                        results.append(BatchResult(path, None, False, error_msg))
                        processed_paths.add(path)
                        completed += 1
                        if progress_callback:
                            progress_callback(completed, total, path.name)
                    else:
                        # Future completed, but timed out from outer loop
                        try:
                            result = future.result(timeout=0)
                            results.append(result)
                            processed_paths.add(path)
                            completed += 1
                            if progress_callback:
                                progress_callback(completed, total, path.name)
                        except Exception as exc:
                            error_msg = str(exc)
                            results.append(BatchResult(path, None, False, error_msg))
                            processed_paths.add(path)
                            completed += 1
                            if progress_callback:
                                progress_callback(completed, total, path.name)

                # Retry logic: resubmit timeout jobs up to max_retries
                if job.max_retries > 1 and timeout_errors:
                    for path in timeout_errors:
                        if retry_queue.get(path, 0) < job.max_retries - 1:
                            retry_count = retry_queue.get(path, 0) + 1
                            retry_queue[path] = retry_count
                            logger.info(
                                "Retrying %s (attempt %d/%d)",
                                path.name,
                                retry_count + 1,
                                job.max_retries,
                            )
                            # Exponential backoff: 2^retry_count * 0.5 seconds
                            backoff = (2 ** retry_count) * 0.5
                            time.sleep(min(backoff, 5.0))  # Cap backoff at 5s

                            # Remove the failed result
                            results = [
                                r for r in results if r.input_path != path
                            ]
                            completed -= 1
                            processed_paths.discard(path)

                            # Resubmit the job
                            new_future = executor.submit(process_one, path)
                            future_map[new_future] = path

                            try:
                                result = new_future.result(timeout=job.timeout)
                                results.append(result)
                                processed_paths.add(path)
                            except concurrent.futures.TimeoutError:
                                error_msg = f"Timeout after {job.max_retries} retries"
                                logger.error(
                                    "Failed to process %s after %d attempts",
                                    path.name,
                                    job.max_retries,
                                )
                                results.append(
                                    BatchResult(path, None, False, error_msg)
                                )
                                processed_paths.add(path)
                            except Exception as exc:
                                logger.error(
                                    "Error retrying %s: %s", path.name, str(exc)
                                )
                                results.append(
                                    BatchResult(path, None, False, str(exc))
                                )
                                processed_paths.add(path)
                            completed += 1
                            if progress_callback:
                                progress_callback(completed, total, path.name)
    finally:
        # Ensure executor shutdown with cleanup
        logger.debug("ThreadPoolExecutor cleanup complete")

    # Riordina risultati nell'ordine originale
    order = {p: i for i, p in enumerate(input_paths)}
    results.sort(key=lambda r: order.get(r.input_path, 0))
    return results


def _dispatch(input_path: Path, output_path: Path, job: BatchJob) -> None:
    """
    Chiama il modulo core corretto in base all'operazione.

    Determina la password corretta per il file:
    1. Se password_map è presente e contiene il file, usa quella
    2. Altrimenti, usa job.password (fallback, backwards compat)

    Se il file è protetto ma non c'è password, raises PDFusionError (explicit, not silent).
    """

    cfg = job.operation_config

    # Determina la password per questo file
    if job.password_map and input_path in job.password_map:
        pwd = job.password_map[input_path]
    else:
        pwd = job.password

    if job.operation == BatchOperation.COMPRESS:
        from core.compress import compress

        compress(input_path, output_path, cfg, pwd)

    elif job.operation == BatchOperation.PROTECT:
        from core.protect import protect

        protect(input_path, output_path, cfg, pwd)

    elif job.operation == BatchOperation.WATERMARK:
        from core.watermark import WatermarkConfig, apply_watermark

        watermark_cfg = cfg if isinstance(cfg, WatermarkConfig) else WatermarkConfig()
        apply_watermark(input_path, output_path, watermark_cfg, pwd)

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

    # Costruisci la lista di password per il merge
    # Se password_map è presente, usa quella; altrimenti fallback a job.password
    if job.password_map:
        passwords = [job.password_map.get(path, job.password) for path in input_paths]
    else:
        passwords = [job.password] * len(input_paths) if job.password else None

    merge(input_paths, output_path, passwords)
