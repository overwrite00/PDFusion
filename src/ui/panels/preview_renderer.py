"""Preview rendering functionality for PDF panels.

Responsibility: Render preview images from PDFs and manage worker thread lifecycle.
"""

import logging
import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


class _PreviewWorker(QObject):
    """Worker that renders a preview PDF in a background thread.

    Signals:
        finished(Path): Emitted when rendering completes successfully.
        error(str): Emitted when rendering fails.
    """

    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(self, render_fn, *args, **kwargs) -> None:
        super().__init__()
        self._render_fn = render_fn
        self._args = args
        self._kwargs = kwargs

    @pyqtSlot()
    def run(self) -> None:
        """Execute the rendering function."""
        try:
            result = self._render_fn(*self._args, **self._kwargs)
            if isinstance(result, Path):
                self.finished.emit(result)
            elif isinstance(result, list) and result and isinstance(result[0], Path):
                self.finished.emit(result[0])
            else:
                self.finished.emit(Path())
        except Exception as exc:
            self.error.emit(f"Errore durante il rendering preview: {exc}")


class PreviewRenderer(QObject):
    """Manages preview rendering with thread-safe lifecycle.

    Responsibility: ONLY preview rendering, worker thread management, and cleanup.

    Signals:
        preview_ready(Path): Emitted when preview is ready and valid.
        preview_failed(str): Emitted when preview generation fails.
    """

    preview_ready = pyqtSignal(Path)
    preview_failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _PreviewWorker | None = None
        self._preview_tmp: Path | None = None
        self._is_rendering = False

    def is_rendering(self) -> bool:
        """Check if a preview is currently being rendered."""
        return self._is_rendering

    def render_preview(
        self,
        render_fn,
        input_path: Path,
        config,
        password: str = "",
    ) -> Path | None:
        """Start an async preview render.

        Args:
            render_fn: Callable that performs the actual PDF rendering.
                Should accept (input_path, output_path, password, config).
            input_path: Input PDF path.
            config: Configuration object for the operation.
            password: PDF password if needed.

        Returns:
            Path to the temporary preview file, or None if rendering is already in progress.
        """
        if self._is_rendering:
            logger.warning("PreviewRenderer: render already in progress, ignoring request")
            return None

        # Create temp file in same directory as input for Windows compatibility
        tmp_dir = input_path.parent
        tmp_fd, tmp_str = tempfile.mkstemp(
            suffix=".pdf", prefix=".pdfusion_preview_", dir=tmp_dir
        )
        os.close(tmp_fd)
        self._preview_tmp = Path(tmp_str)

        self._is_rendering = True

        # Start worker thread
        self._thread = QThread(self)
        self._worker = _PreviewWorker(
            render_fn,
            input_path,
            self._preview_tmp,
            password,
            config,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_render_finished)
        self._worker.error.connect(self._on_render_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

        return self._preview_tmp

    @pyqtSlot(Path)
    def _on_render_finished(self, result_path: Path) -> None:
        """Internal slot called when rendering completes."""
        self._is_rendering = False
        try:
            # Check if file exists and is not empty
            if result_path.exists() and result_path.stat().st_size > 0:
                # Guard against stale signals: if _preview_tmp was cleared
                # (e.g., by cancel_render), discard this result
                if self._preview_tmp is None:
                    try:
                        result_path.unlink()
                    except OSError:
                        pass
                    return

                preview_path = self._preview_tmp
                self._preview_tmp = None
                self.preview_ready.emit(preview_path)
            else:
                # Empty or missing file
                self.preview_failed.emit("Anteprima non disponibile per questa operazione.")
                self._cleanup_temp_file()
        except Exception as e:
            logger.error(f"PreviewRenderer: error in render finished: {e}", exc_info=True)
            self.preview_failed.emit(f"Errore interno durante preview: {e}")
            self._cleanup_temp_file()

    @pyqtSlot(str)
    def _on_render_error(self, error_msg: str) -> None:
        """Internal slot called when rendering fails."""
        self._is_rendering = False
        self.preview_failed.emit(error_msg)
        self._cleanup_temp_file()

    def cancel_render(self) -> None:
        """Cancel the current preview render and clean up.

        CRITICAL FIX: Never use terminate() on Linux/macOS (pthread_cancel
        on fitz-blocked threads causes permanent deadlock). Use only quit().
        """
        import sys

        if self._thread and self._thread.isRunning():
            logger.debug("PreviewRenderer: cancelling render")
            self._thread.quit()
            # Wait up to 3 seconds for graceful shutdown (polling every 100ms)
            for _ in range(30):  # 30 * 100ms = 3 seconds
                if self._thread.wait(100):
                    logger.debug("PreviewRenderer: render thread stopped via quit")
                    break
            else:
                # Timeout on Linux/macOS: don't use terminate()
                if sys.platform in ("linux", "darwin"):
                    logger.warning(
                        "PreviewRenderer: render thread did not stop. "
                        "Not using terminate() on Linux/macOS (deadlock risk)."
                    )
                else:
                    # Windows: safe to terminate as fallback
                    logger.warning("PreviewRenderer: render thread did not respond to quit, forcing termination")
                    self._thread.terminate()
                    self._thread.wait(1000)
            logger.debug("PreviewRenderer: render thread stopped")

        self._is_rendering = False
        self._cleanup_temp_file()

    def _cleanup_temp_file(self) -> None:
        """Clean up the temporary preview file."""
        if self._preview_tmp:
            if self._preview_tmp.exists():
                try:
                    logger.debug(f"PreviewRenderer: deleting temp file {self._preview_tmp}")
                    self._preview_tmp.unlink()
                except OSError as e:
                    logger.warning(f"PreviewRenderer: failed to delete temp file: {e}")
            self._preview_tmp = None

        self._thread = None
        self._worker = None
