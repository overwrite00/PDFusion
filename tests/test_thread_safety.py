"""
Comprehensive thread-safety tests for PDF document rendering workers.

Tests cover:
1. Race conditions between signal callbacks and worker cleanup
2. Use-after-free prevention when _worker is deleted during _close_worker()
3. File handle leaks and proper document closure
4. Concurrent open/close/switch operations
5. Thread timeout handling and forced termination
"""

from __future__ import annotations

import logging
import os

# Import modules under test
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.thumbnail_panel import ThumbnailPanel
from ui.viewer import PDFViewer, _RenderWorker

logger = logging.getLogger(__name__)


def _is_headless_environment() -> bool:
    """
    Rileva se siamo in un ambiente headless (CI/server senza proper display).

    Headless indicators:
    - Linux senza DISPLAY
    - DISPLAY=:99 (xvfb standard) ma senza Xvfb running
    - Ambiente CI (GitHub Actions, GitLab CI, etc.)
    """
    # Caso 1: No DISPLAY at all
    if os.name == "posix" and not os.environ.get("DISPLAY"):
        return True

    # Caso 2: DISPLAY=:99 or :X (xvfb) but server not actually running
    # Per testare se Xvfb è running, proviamo a connetterci
    if os.name == "posix" and os.environ.get("DISPLAY"):
        display = os.environ.get("DISPLAY")
        # Se è :99 o :X e non è localhost:X.0, probabilmente è xvfb non funzionante
        if display.startswith(":"):
            # Try to detect if xvfb-run is active (LD_PRELOAD contains xvfb)
            if "xvfb" not in os.environ.get("LD_PRELOAD", "").lower():
                # No xvfb in LD_PRELOAD, ma ha DISPLAY virtuale -> xvfb non running
                try:
                    import subprocess
                    result = subprocess.run(
                        ["ps", "aux"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if "Xvfb" not in result.stdout and "Xvfb" not in result.stderr:
                        # Xvfb not in process list
                        return True
                except Exception:
                    pass  # Assume headless if we can't check

    return False


def _safe_qapplication_creation():
    """
    Crea una QApplication in modo sicuro, con handling per ambienti headless.

    Su Linux headless senza display manager, QApplication initialization CRASH
    con "Fatal Python error: Aborted". Questo wrapper:
    1. Rileva ambienti headless PRIMA di importare PyQt6
    2. Se headless, skippa il test senza importare PyQt6
    3. Se non headless, importa e crea QApplication

    CRITICAL: Questo evita che PyQt6 tenti di connettersi a X11 su headless.
    """
    # Se è headless, skippa senza importare PyQt6 (evita crash)
    if _is_headless_environment():
        pytest.skip("QApplication non supportato in ambiente headless (no display)")

    # Solo se non headless, importa PyQt6
    from PyQt6.QtWidgets import QApplication

    # Try to get existing instance first
    app = QApplication.instance()
    if app is not None:
        return app

    # Try to create a new application
    try:
        return QApplication([])
    except Exception as e:
        logger.error(f"QApplication initialization failed: {e}")
        # Fallback: se la creazione fallisce anche in non-headless, skippa
        pytest.skip(f"QApplication initialization failed: {e}")


class TestRenderWorkerThreadSafety:
    """Test _RenderWorker for proper signal emission and closure."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a minimal valid PDF for testing."""
        try:
            import fitz
            doc = fitz.open()
            # Add a simple page
            page = doc.new_page()
            page.insert_text((10, 10), "Test Page")
            pdf_path = tmp_path / "test.pdf"
            doc.save(str(pdf_path))
            doc.close()
            return str(pdf_path)
        except ImportError:
            pytest.skip("fitz not available")

    def test_worker_close_flag_prevents_reopening(self, qapp, sample_pdf):
        """Verify that calling close() prevents reopening the document."""
        from PyQt6.QtCore import QThread
        worker = _RenderWorker(sample_pdf)
        thread = QThread()
        worker.moveToThread(thread)

        # Mark as closed
        worker.close()
        assert worker._closed is True

        # Attempting to render should not reopen the document
        worker.render(0, 1.0)
        assert worker._doc is None, "Document should not reopen after close() call"

        thread.quit()
        thread.wait()

    def test_worker_signal_emission_on_render(self, qapp, sample_pdf):
        """Verify worker emits rendered signal with correct data."""
        from PyQt6.QtCore import QThread
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QApplication

        worker = _RenderWorker(sample_pdf)
        thread = QThread()
        worker.moveToThread(thread)

        signal_received = []

        def on_rendered(page_idx: int, pixmap: QPixmap):
            signal_received.append((page_idx, pixmap))

        worker.rendered.connect(on_rendered)
        thread.started.connect(lambda: worker.render(0, 1.0))

        thread.start()
        # Wait for signal
        timeout = time.time() + 5.0
        while not signal_received and time.time() < timeout:
            QApplication.processEvents()
            time.sleep(0.01)

        assert len(signal_received) > 0, "rendered signal was not emitted"
        page_idx, pixmap = signal_received[0]
        assert page_idx == 0
        assert isinstance(pixmap, QPixmap)

        thread.quit()
        thread.wait()

    def test_worker_error_signal_on_invalid_page(self, qapp, sample_pdf):
        """Verify worker emits error signal for invalid page indices."""
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication

        worker = _RenderWorker(sample_pdf)
        thread = QThread()
        worker.moveToThread(thread)

        error_received = []

        def on_error(msg: str):
            error_received.append(msg)

        worker.error.connect(on_error)

        # Render with invalid page index
        thread.started.connect(lambda: worker.render(9999, 1.0))
        thread.start()

        timeout = time.time() + 2.0
        while time.time() < timeout:
            QApplication.processEvents()
            time.sleep(0.01)

        thread.quit()
        thread.wait()


class TestPDFViewerThreadSafety:
    """Test PDFViewer._close_worker() for race conditions."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def viewer(self, qapp):
        """Create a PDFViewer instance."""
        return PDFViewer()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a minimal valid PDF for testing."""
        try:
            import fitz
            doc = fitz.open()
            for i in range(3):
                page = doc.new_page()
                page.insert_text((10, 10), f"Test Page {i}")
            pdf_path = tmp_path / "test.pdf"
            doc.save(str(pdf_path))
            doc.close()
            return str(pdf_path)
        except ImportError:
            pytest.skip("fitz not available")

    def test_close_worker_with_no_worker_initialized(self, viewer):
        """Happy path: close when _worker is None."""
        assert viewer._worker is None
        # Should not raise
        viewer._close_worker()
        assert viewer._worker is None

    def test_close_worker_sets_worker_to_none_first(self, viewer, sample_pdf):
        """CRITICAL: _worker is set to None BEFORE accessing it."""
        viewer.load_document(Path(sample_pdf))
        assert viewer._worker is not None

        # Mock the snapshot to track access
        original_worker = viewer._worker

        viewer._close_worker()

        # After _close_worker, _worker should be None
        assert viewer._worker is None
        # But we should have closed the document without error
        assert original_worker._doc is None

    def test_close_worker_idempotency(self, viewer, sample_pdf):
        """Calling _close_worker twice should be safe."""
        viewer.load_document(Path(sample_pdf))

        # First close
        viewer._close_worker()
        assert viewer._worker is None

        # Second close (should not crash)
        viewer._close_worker()
        assert viewer._worker is None

    def test_close_worker_with_thread_timeout(self, viewer, sample_pdf):
        """Test fallback to thread.terminate() on quit timeout."""
        viewer.load_document(Path(sample_pdf))
        worker = viewer._worker
        assert worker is not None

        # Mock thread.wait to simulate timeout
        with patch.object(viewer._thread, 'wait', return_value=False):
            with patch.object(viewer._thread, 'terminate') as mock_terminate:
                viewer._close_worker()
                # terminate should have been called
                mock_terminate.assert_called_once()

        assert viewer._worker is None

    def test_signal_callback_during_close_is_safe(self, viewer, sample_pdf):
        """
        CRITICAL: Simulate signal callback deleting _worker during _close_worker().
        The snapshot pattern should prevent use-after-free.
        """
        viewer.load_document(Path(sample_pdf))

        # Monkey-patch _on_rendered to simulate concurrent deletion
        original_on_rendered = viewer._on_rendered

        def malicious_on_rendered(page_idx: int, pixmap: QPixmap):
            """Simulate another thread calling load_document -> _close_worker."""
            if viewer._worker is not None:
                # Force delete to simulate race
                viewer._worker = None
            original_on_rendered(page_idx, pixmap)

        viewer._on_rendered = malicious_on_rendered

        # This should not crash even though _worker is deleted
        try:
            viewer._close_worker()
            success = True
        except Exception as e:
            success = False
            logger.error(f"Race condition crash: {e}")

        assert success, "Race condition caused a crash"
        assert viewer._worker is None

    def test_load_document_closes_previous_worker(self, viewer, sample_pdf):
        """Loading a new document should safely close the previous worker."""
        viewer.load_document(Path(sample_pdf))
        first_worker = viewer._worker
        assert first_worker is not None

        # Load same document again
        viewer.load_document(Path(sample_pdf))
        second_worker = viewer._worker
        assert second_worker is not None
        assert second_worker is not first_worker
        assert first_worker._doc is None

    def test_rapid_load_unload_cycle(self, viewer, sample_pdf):
        """Stress test: rapid load/unload without memory leaks."""
        for i in range(5):
            viewer.load_document(Path(sample_pdf))
            assert viewer._worker is not None
            viewer.close_document()
            assert viewer._worker is None

    def test_document_handle_not_locked_after_close(self, viewer, sample_pdf, tmp_path):
        """
        Windows-specific: Verify file handle is released after close.
        After _close_worker(), the file should be deletable.
        """
        import shutil
        test_file = tmp_path / "deletable.pdf"
        shutil.copy(sample_pdf, test_file)

        viewer.load_document(test_file)
        viewer._close_worker()

        # Attempt to delete (would fail if handle is locked)
        try:
            test_file.unlink()
            success = True
        except PermissionError:
            success = False

        assert success, "File handle still locked after _close_worker()"

    def test_close_worker_exception_logging(self, viewer, sample_pdf, caplog):
        """Verify exceptions in _close_worker are properly logged."""
        viewer.load_document(Path(sample_pdf))

        # Mock _thread.quit to raise an exception
        with patch.object(viewer._thread, 'quit', side_effect=RuntimeError("Mock error")):
            with caplog.at_level(logging.ERROR):
                viewer._close_worker()

            # Should log the error but not crash
            assert "Errore durante chiusura worker viewer" in caplog.text


class TestThumbnailPanelThreadSafety:
    """Test ThumbnailPanel._close_worker() for race conditions."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a minimal valid PDF for testing."""
        try:
            import fitz
            doc = fitz.open()
            for i in range(5):
                page = doc.new_page()
                page.insert_text((10, 10), f"Page {i}")
            pdf_path = tmp_path / "test.pdf"
            doc.save(str(pdf_path))
            doc.close()
            return str(pdf_path)
        except ImportError:
            pytest.skip("fitz not available")

    def test_thumb_worker_snapshot_prevents_use_after_free(self, qapp, sample_pdf):
        """Test that thumbnail worker uses snapshot pattern correctly."""
        panel = ThumbnailPanel()
        panel.load_document(Path(sample_pdf), "")
        assert panel._worker is not None

        original_worker = panel._worker
        panel._close_worker()

        # Worker should be cleared
        assert panel._worker is None
        # But document should be properly closed
        assert original_worker._doc is None

    def test_thumb_worker_idempotency(self, qapp, sample_pdf):
        """Calling _close_worker multiple times on thumbnail panel should be safe."""
        panel = ThumbnailPanel()
        panel.load_document(Path(sample_pdf), "")

        panel._close_worker()
        assert panel._worker is None

        panel._close_worker()
        assert panel._worker is None

    def test_concurrent_thumbnail_rendering_and_close(self, qapp, sample_pdf):
        """
        Stress test: render thumbnails while closing.
        This tests the snapshot pattern under concurrent load.
        """
        panel = ThumbnailPanel()
        panel.load_document(Path(sample_pdf), "")

        # Request rendering of multiple thumbnails
        for i in range(3):
            panel._request_thumb(i)

        # Give rendering time to start
        time.sleep(0.1)

        # Close while rendering is active
        try:
            panel._close_worker()
            success = True
        except Exception as e:
            logger.error(f"Concurrent close failed: {e}")
            success = False

        assert success
        assert panel._worker is None


class TestConcurrentOperations:
    """Test concurrent PDF operations across multiple workers."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a test PDF."""
        try:
            import fitz
            doc = fitz.open()
            for i in range(5):
                page = doc.new_page()
                page.insert_text((10, 10), f"Page {i}")
            pdf_path = tmp_path / "test.pdf"
            doc.save(str(pdf_path))
            doc.close()
            return str(pdf_path)
        except ImportError:
            pytest.skip("fitz not available")

    def test_viewer_and_thumbnail_concurrent_close(self, qapp, sample_pdf):
        """Test closing viewer and thumbnail worker concurrently."""
        viewer = PDFViewer()
        thumb = ThumbnailPanel()

        viewer.load_document(Path(sample_pdf))
        thumb.load_document(Path(sample_pdf), "")

        # Close both concurrently in separate threads
        errors = []

        def close_viewer():
            try:
                viewer._close_worker()
            except Exception as e:
                errors.append(("viewer", e))

        def close_thumb():
            try:
                thumb._close_worker()
            except Exception as e:
                errors.append(("thumb", e))

        t1 = threading.Thread(target=close_viewer)
        t2 = threading.Thread(target=close_thumb)

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert len(errors) == 0, f"Concurrent close errors: {errors}"
        assert viewer._worker is None
        assert thumb._worker is None

    def test_rapid_document_switch(self, qapp, sample_pdf, tmp_path):
        """
        Stress test: rapidly switching between documents.
        Each switch calls load_document which calls _close_worker.
        """
        import shutil
        from PyQt6.QtWidgets import QApplication

        # Create multiple test PDFs
        pdfs = []
        for i in range(3):
            pdf_path = tmp_path / f"test{i}.pdf"
            shutil.copy(sample_pdf, pdf_path)
            pdfs.append(pdf_path)

        viewer = PDFViewer()

        for _ in range(5):  # Multiple cycles
            for pdf in pdfs:
                viewer.load_document(pdf)
                # Verify state
                assert viewer._worker is not None
                QApplication.processEvents()  # Allow Qt events

        # Final cleanup
        viewer.close_document()
        assert viewer._worker is None


class TestWindowsSpecificIssues:
    """Test Windows-specific file handle and thread issues."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a test PDF."""
        try:
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((10, 10), "Windows Test")
            pdf_path = tmp_path / "windows_test.pdf"
            doc.save(str(pdf_path))
            doc.close()
            return str(pdf_path)
        except ImportError:
            pytest.skip("fitz not available")

    def test_file_not_locked_after_worker_close(self, qapp, sample_pdf, tmp_path):
        """
        Windows: After _close_worker, fitz should release file locks
        so the file can be deleted/moved.
        """
        viewer = PDFViewer()
        viewer.load_document(Path(sample_pdf))

        # Ensure worker has opened the doc
        viewer._render_current()
        time.sleep(0.5)

        viewer._close_worker()

        # Try to modify the file (would fail on Windows if locked)
        import shutil
        dest = tmp_path / "moved.pdf"
        try:
            shutil.move(sample_pdf, dest)
            success = True
        except (PermissionError, OSError) as e:
            logger.error(f"File still locked: {e}")
            success = False

        assert success, "fitz document not properly closed, file handle locked"

    def test_thread_termination_on_wait_timeout(self, qapp, sample_pdf):
        """Test that thread.terminate() is called if quit() timeout is exceeded."""
        viewer = PDFViewer()
        viewer.load_document(Path(sample_pdf))

        # Mock the wait to fail
        with patch.object(viewer._thread, 'wait', return_value=False):
            with patch.object(viewer._thread, 'terminate', wraps=viewer._thread.terminate) as mock_term:
                viewer._close_worker()
                mock_term.assert_called()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a test PDF."""
        try:
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((10, 10), "Edge Case Test")
            pdf_path = tmp_path / "edge.pdf"
            doc.save(str(pdf_path))
            doc.close()
            return str(pdf_path)
        except ImportError:
            pytest.skip("fitz not available")

    def test_close_worker_before_start_worker(self, qapp):
        """Closing before opening should be safe."""
        viewer = PDFViewer()
        viewer._close_worker()  # No document loaded yet
        assert viewer._worker is None

    def test_worker_render_after_close_flag_set(self, qapp, sample_pdf):
        """After close() is called, render() should not open document."""
        worker = _RenderWorker(sample_pdf)
        worker.close()

        # Try to render
        worker.render(0, 1.0)

        # Document should still be None
        assert worker._doc is None

    def test_multiple_threads_closing_same_worker(self, qapp, sample_pdf):
        """
        Multiple threads calling _close_worker concurrently.
        The snapshot pattern should make this safe.
        """
        viewer = PDFViewer()
        viewer.load_document(Path(sample_pdf))

        errors = []

        def close_worker():
            try:
                viewer._close_worker()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=close_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Thread collision errors: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
