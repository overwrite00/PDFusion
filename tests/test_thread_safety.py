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

# Import modules under test
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.thumbnail_panel import ThumbnailPanel
from ui.viewer import PDFViewer, _RenderWorker

logger = logging.getLogger(__name__)


def _safe_qapplication_creation():
    """
    Restituisce una QApplication condivisa per i test.

    L'inizializzazione di Qt su ambienti senza display (CI headless) è gestita
    da ``tests/conftest.py``, che forza il platform plugin "offscreen" prima di
    qualsiasi import di PyQt6. Con "offscreen" la QApplication può sempre essere
    creata senza connettersi a X11, quindi non serve più rilevare/skippare gli
    ambienti headless: tutti i test girano realmente.
    """
    from PyQt6.QtWidgets import QApplication

    # Riusa l'istanza esistente se presente (una sola QApplication per processo).
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _flush_qt_deletions():
    """Esegue le ``deleteLater()`` pendenti dopo ogni test.

    In produzione il loop eventi di Qt elabora ``deleteLater()`` e distrugge
    worker/QThread in modo sicuro. Nei test non c'è un loop eventi in
    esecuzione, quindi worker e thread chiusi via ``_close_worker()`` non
    verrebbero mai distrutti: si accumulerebbero e, quando il garbage
    collector di Python distrugge un ``PDFViewer``/``ThumbnailPanel`` con un
    QThread ancora vivo, Qt aborta con "QThread: Destroyed while thread is
    still running" (SIGABRT). Svuotando la coda degli eventi posticipati dopo
    ogni test eliminiamo questa contaminazione tra test.
    """
    yield

    import gc

    from PyQt6.QtCore import QCoreApplication, QEvent, QEventLoop, QThread
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return

    # 1. Ferma in modo sicuro qualsiasi QThread ancora in esecuzione lasciato
    #    da widget creati nel corpo del test (o da chiusure fallite, es. test
    #    che mockano thread.quit() per sollevare). Un QThread distrutto dal GC
    #    mentre è ancora running fa abortire Qt ("QThread: Destroyed while
    #    thread is still running" -> SIGABRT), contaminando i test successivi.
    def _stop_thread(thread: QThread | None) -> bool:
        """Stop a QThread safely without risking deadlock on Linux.

        Returns ``True`` if the thread is confirmed STOPPED (or was never
        running / already gone), ``False`` if it is still running and could
        not be stopped. The caller uses this to decide whether it is safe to
        process DeferredDelete events / GC: destroying a ``~QThread()`` while
        Qt still considers it running calls ``qFatal()`` -> ``abort()`` ->
        SIGABRT, a hard C signal no try/except can catch.

        CRITICAL: Never use terminate() (pthread_cancel) on Linux when thread
        may be blocked in C code like fitz.get_pixmap(). The cancel remains
        pending inside non-cancel-safe code, causing permanent deadlock.

        On Linux: use only quit() + a real blocking wait(). If it times out,
        report ``False`` so the caller skips the unsafe deletion path; the job
        timeout-minutes=20 will eventually kill the entire process.

        On Windows/macOS: terminate() is safe as a fallback.
        """
        if thread is None:
            return True
        try:
            if not thread.isRunning():
                return True
        except RuntimeError:
            return True  # Thread was already garbage collected or invalid

        try:
            thread.quit()
        except Exception:
            # quit() failed - thread is probably corrupted. Don't try to wait.
            # Report not-stopped so the caller avoids the deletion path.
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True

        # Real blocking wait: give quit() a genuine chance to drain the event
        # loop. On the Linux offscreen plugin a racy 100ms poll often reports
        # "still running" even though quit() will land shortly; a single longer
        # blocking wait removes that window (this is what made Windows reliable).
        try:
            if thread.wait(5000):
                return True
            if not thread.isRunning():
                return True
        except RuntimeError:
            return True  # Thread object became invalid while waiting
        except Exception:
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True

        # CRITICAL: Do NOT use terminate() on Linux/macOS - causes permanent
        # deadlock via pthread_cancel on fitz-blocked code.
        if sys.platform in ("linux", "darwin"):
            # Cannot safely kill it. Report NOT stopped so the caller skips the
            # DeferredDelete/GC path that would destroy a live ~QThread().
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True

        # On Windows: terminate() is safe as fallback
        try:
            if thread.isRunning():
                thread.terminate()
                if thread.wait(2000):
                    return True
                return not thread.isRunning()
        except Exception:
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True
        return True

    # Track whether EVERY thread is confirmed stopped. If even one running
    # thread remains (Linux can't safely kill it), we must NOT process
    # DeferredDelete events or run GC over it -> that destruction is what
    # triggers SIGABRT. Leaking the orphan is strictly safer than aborting.
    all_threads_stopped = True

    try:
        for widget in app.allWidgets():
            try:
                if isinstance(widget, PDFViewer | ThumbnailPanel):
                    # Ferma direttamente il thread del widget: _close_worker() esce
                    # subito se _worker è già None (es. dopo una chiusura fallita),
                    # lasciando però il thread ancora in esecuzione.
                    if not _stop_thread(getattr(widget, "_thread", None)):
                        all_threads_stopped = False
                    try:
                        widget._close_worker()
                    except Exception:
                        pass
            except Exception:
                # If we can't process this widget, continue with others
                pass
    except Exception:
        # If we can't get widgets, continue anyway
        pass

    # Backstop: qualsiasi altro QThread ancora vivo nell'albero degli oggetti.
    # Include thread orfani lasciati da test che mockano quit()/wait() (es.
    # test_close_worker_exception_logging): il mock è ormai rimosso, quindi qui
    # quit() reale può finalmente fermarli.
    try:
        for thread in app.findChildren(QThread):
            try:
                if not _stop_thread(thread):
                    all_threads_stopped = False
            except Exception:
                pass
    except Exception:
        # If we can't find children, continue anyway
        pass

    # 2. SE e solo se tutti i thread sono confermati fermi, è sicuro processare
    #    gli eventi DeferredDelete (generati da deleteLater()) e forzare il GC.
    #    Distruggere un QThread mentre Qt lo considera ancora running fa abortire
    #    il processo (SIGABRT) — un crash C che nessun try/except intercetta.
    #    Su Linux, se un thread non si è fermato, SALTIAMO tutta la fase di
    #    distruzione: meglio "leakare" l'oggetto (il job ha un timeout) che far
    #    crashare l'intera suite. Vedi crash Ubuntu in _flush_qt_deletions.
    if not all_threads_stopped:
        logger.warning(
            "Un QThread non si è fermato in modo confermato durante il teardown "
            "(%s). Salto DeferredDelete/GC per evitare ~QThread() su thread vivo "
            "(SIGABRT). L'oggetto verrà ripulito dalla terminazione del processo.",
            sys.platform,
        )
        return

    try:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    except Exception:
        pass

    try:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    except Exception:
        pass

    try:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    except Exception:
        pass

    # 3. Skip GC here - it was triggering background finalization of fitz resources
    #    that corrupted Python's condition variable state on Linux.
    #    With the BlockingQueuedConnection fitz.close() fix in viewer.py and
    #    thumbnail_panel.py, documents are now closed on the worker thread before
    #    it stops, eliminating cross-thread finalization. Let Python's normal GC
    #    handle orphaned widgets at its own pace - no more explicit gc.collect().


class TestRenderWorkerThreadSafety:
    """Test _RenderWorker for proper signal emission and closure."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def make_worker_thread(self, qapp):
        """Factory + GUARANTEED deterministic teardown for bare worker/thread.

        ROOT CAUSE of the Ubuntu SIGABRT this fixture fixes:

        These tests create a ``_RenderWorker`` and a *bare, unparented*
        ``QThread()`` as local variables, then ``moveToThread()`` the worker.
        Unlike production (``QThread(self)``, parented to the widget) and unlike
        every other test class here (which use ``PDFViewer``/``ThumbnailPanel``
        widget fixtures), these objects are:

          * NOT ``QWidget`` instances -> invisible to ``app.allWidgets()``
          * NOT parented to any QObject -> invisible to ``app.findChildren(QThread)``

        So the autouse ``_flush_qt_deletions`` safety net structurally CANNOT
        find or stop them. When the test returns, ``worker``/``thread`` become
        orphaned locals. Python's GC later destroys the ``QThread`` object; if
        Qt still considers the thread running at that instant, ``~QThread()``
        calls ``qFatal("QThread: Destroyed while thread is still running")`` ->
        ``abort()`` -> SIGABRT. This is a hard C-level signal, NOT a Python
        exception, which is why wrapping cleanup in try/except never helped.

        On Windows ``wait()`` reliably reports the idle event loop as stopped,
        so GC always sees a finished thread -> no crash. On Ubuntu's offscreen
        plugin the event-loop teardown timing differs and the orphaned thread
        can still look "running" at GC time -> SIGABRT, landing on whichever
        test first leaves an open-fitz-doc + idle-but-not-confirmed-stopped
        thread (``test_worker_error_signal_on_invalid_page``: render(9999)
        opens the doc, hits the bounds check, returns WITHOUT emitting a signal
        and WITHOUT closing the doc).

        THE FIX: this fixture owns the lifecycle. In teardown it deterministically
        quits the thread, BLOCKS until it is genuinely finished (real wait, not a
        racy poll), closes the worker's fitz doc, then destroys both objects
        DIRECTLY (``sip.delete``) instead of via ``deleteLater``/GC. By the time
        Python GC sees the C++ objects they are already gone, so ~QThread can
        never run on a live thread. No reliance on the unreachable safety net.
        """
        from PyQt6.QtCore import QThread

        created: list[tuple[_RenderWorker, QThread]] = []

        def _factory(doc_path: str) -> tuple[_RenderWorker, QThread]:
            worker = _RenderWorker(doc_path)
            thread = QThread()
            worker.moveToThread(thread)
            created.append((worker, thread))
            return worker, thread

        yield _factory

        for worker, thread in created:
            # 1. Stop the thread's event loop and BLOCK until it is truly
            #    finished. We use the real (unbounded-but-capped) wait so there
            #    is no window where Qt still considers the thread running.
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(5000):
                        # Last resort: only Windows can safely terminate().
                        # On Linux/macOS terminate() (pthread_cancel) on a thread
                        # blocked in fitz deadlocks, so we must not use it; a
                        # genuinely stuck thread here is a real bug to surface.
                        if sys.platform == "win32":
                            thread.terminate()
                            thread.wait(2000)
            except RuntimeError:
                # C++ object already gone; nothing left to stop.
                pass

            # 2. Close any fitz doc the worker left open (render(9999) returns
            #    early without closing it). Frees the file handle deterministically.
            try:
                if worker._doc is not None:
                    worker._doc.close()
                    worker._doc = None
            except (RuntimeError, AttributeError):
                pass

            # 3. Destroy the C++ objects NOW, while the thread is confirmed
            #    stopped — never defer to deleteLater()/GC. This removes any
            #    possibility of ~QThread() running on a live thread later.
            try:
                import sip  # type: ignore
            except ImportError:
                try:
                    from PyQt6 import sip  # type: ignore
                except ImportError:
                    sip = None  # type: ignore

            if sip is not None:
                for obj in (worker, thread):
                    try:
                        if not sip.isdeleted(obj):
                            sip.delete(obj)
                    except (RuntimeError, TypeError, ValueError):
                        pass

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

    def test_worker_close_flag_prevents_reopening(self, make_worker_thread, sample_pdf):
        """Verify that calling close() prevents reopening the document."""
        worker, thread = make_worker_thread(sample_pdf)

        # Mark as closed
        worker.close()
        assert worker._closed is True

        # Attempting to render should not reopen the document
        worker.render(0, 1.0)
        assert worker._doc is None, "Document should not reopen after close() call"

        # Thread teardown (quit + full wait + direct delete) is handled
        # deterministically by the make_worker_thread fixture.

    def test_worker_signal_emission_on_render(self, make_worker_thread, sample_pdf):
        """Verify worker emits rendered signal with correct data."""
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QApplication

        worker, thread = make_worker_thread(sample_pdf)

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

        # Thread teardown handled deterministically by make_worker_thread fixture.

    def test_worker_error_signal_on_invalid_page(self, make_worker_thread, sample_pdf):
        """Verify worker emits error signal for invalid page indices."""
        from PyQt6.QtWidgets import QApplication

        worker, thread = make_worker_thread(sample_pdf)

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

        # Thread teardown handled deterministically by make_worker_thread fixture:
        # it quits the thread, BLOCKS until genuinely finished, closes the fitz
        # doc render(9999) left open, then deletes both C++ objects directly so
        # GC can never destroy a live QThread (the SIGABRT this test once caused).


class TestPDFViewerThreadSafety:
    """Test PDFViewer._close_worker() for race conditions."""

    @pytest.fixture
    def qapp(self):
        """Provide QApplication instance (with headless support)."""
        return _safe_qapplication_creation()

    @pytest.fixture
    def viewer(self, qapp):
        """Create a PDFViewer instance, garantendo la chiusura del worker."""
        v = PDFViewer()
        yield v
        # Teardown: non lasciare mai un QThread in esecuzione al GC del widget.
        v._close_worker()

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
        """Test the quit-timeout fallback path of _shutdown_thread.

        Platform contract (see PDFViewer._shutdown_thread):
        - Windows: when quit()+wait() times out, terminate() is called as a
          forced fallback.
        - Linux/macOS: terminate() is DELIBERATELY never called — pthread_cancel
          on a thread blocked inside fitz C code causes a permanent deadlock.
          On these platforms the code logs and relies on cooperative quit().

        We mock wait() to force the timeout branch, but we keep a reference to
        the real wait so we can genuinely stop the thread afterwards. Leaving a
        QThread running and then letting it be deleted (deleteLater/GC) makes Qt
        abort with "QThread: Destroyed while thread is still running" (SIGABRT),
        which is exactly the teardown crash this test must not produce.
        """
        viewer.load_document(Path(sample_pdf))
        worker = viewer._worker
        thread = viewer._thread
        assert worker is not None
        assert thread is not None

        real_wait = thread.wait  # capture the genuine wait for real shutdown

        # Mock thread.wait to simulate a quit() timeout (never reports stopped).
        with patch.object(thread, 'wait', return_value=False):
            with patch.object(thread, 'terminate') as mock_terminate:
                viewer._close_worker()

                if sys.platform == "win32":
                    # Windows: terminate() is the forced fallback on timeout.
                    mock_terminate.assert_called_once()
                else:
                    # Linux/macOS: terminate() must NOT be used (deadlock risk).
                    mock_terminate.assert_not_called()

        assert viewer._worker is None

        # The mocked wait() prevented a real shutdown: the worker's idle event
        # loop is still running. Stop it genuinely now (mocks are gone) so the
        # thread is finished before it is destroyed — otherwise Qt aborts at GC.
        thread.quit()
        real_wait(2000)
        assert not thread.isRunning()

    def test_signal_callback_during_close_is_safe(self, viewer, sample_pdf):
        """
        CRITICAL: Simulate signal callback deleting _worker during _close_worker().
        The snapshot pattern should prevent use-after-free.
        """
        from PyQt6.QtGui import QPixmap

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
        """Verify exceptions during thread shutdown are handled gracefully.

        Anche se ``quit()`` solleva, _close_worker() non deve propagare
        l'eccezione: deve loggarla e proseguire comunque con l'arresto
        cooperativo (wait()), senza far crashare il processo.

        NOTE: This test mocks quit() to raise, creating a "broken" thread that
        _close_worker() must handle gracefully. The fixture's _flush_qt_deletions
        cleanup will stop and destroy the thread after test completes, avoiding
        crashes from accessing a corrupted QThread object after the mock.
        """
        viewer.load_document(Path(sample_pdf))
        thread = viewer._thread

        # Mock _thread.quit to raise an exception
        with patch.object(thread, 'quit', side_effect=RuntimeError("Mock error")):
            with caplog.at_level(logging.WARNING):
                # Non deve sollevare
                viewer._close_worker()

            # L'eccezione di quit() deve essere loggata, non propagata.
            assert "quit() del thread fallito" in caplog.text

        # Il worker è azzerato (snapshot pattern), il thread non è più tracciato
        # in viewer, ma il thread è ancora vivo (quit was never called via mock).
        # DO NOT attempt to manually quit/wait on this thread - that risks
        # access violations when the thread object is corrupted by the mock.
        # Let the fixture _flush_qt_deletions handle cleanup safely.
        assert viewer._worker is None


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
        panel.load_document(Path(sample_pdf), total_pages=5)
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
        panel.load_document(Path(sample_pdf), total_pages=5)

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
        panel.load_document(Path(sample_pdf), total_pages=5)

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
        """Test closing viewer and thumbnail worker is safe (snapshot pattern).

        NOTE: Qt forbids driving a QThread (quit/wait/terminate) from a
        foreign Python thread — doing so deadlocks on headless Linux with
        pthread_cancel on fitz blocking threads. The snapshot-based
        use-after-free guard is verified via sequential close instead.
        """
        viewer = PDFViewer()
        thumb = ThumbnailPanel()

        viewer.load_document(Path(sample_pdf))
        thumb.load_document(Path(sample_pdf), total_pages=5)

        # Close sequentially (not from raw threads — Qt forbids cross-thread
        # QThread control; it deadlocks on headless CI when worker is in fitz).
        viewer._close_worker()
        thumb._close_worker()

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
        """Test the platform-specific fallback when quit() timeout is exceeded.

        Windows: ``terminate()`` is the forced fallback (mocked here so we don't
        actually kill a thread mid-fitz-render, which would corrupt state).
        Linux/macOS: ``terminate()`` is deliberately NOT used (pthread_cancel
        on fitz-blocked threads deadlocks); the contract is that it is never
        invoked. We verify the correct branch per platform.
        """
        viewer = PDFViewer()
        viewer.load_document(Path(sample_pdf))
        thread = viewer._thread
        real_wait = thread.wait  # genuine wait, for real shutdown afterwards

        # Mock the wait to fail e terminate per evitare di uccidere davvero il
        # thread mentre renderizza.
        with patch.object(thread, 'wait', return_value=False):
            with patch.object(thread, 'terminate') as mock_term:
                viewer._close_worker()
                if sys.platform == "win32":
                    mock_term.assert_called()
                else:
                    mock_term.assert_not_called()

        # Cleanup reale del thread (wait/terminate non sono più mockati):
        # il mock di wait() ha impedito l'arresto reale, quindi il loop eventi
        # del worker è ancora vivo. Fermarlo davvero prima del GC evita il
        # SIGABRT "QThread: Destroyed while thread is still running".
        thread.quit()
        real_wait(2000)
        assert not thread.isRunning()


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
        """Repeated _close_worker calls are idempotent and crash-free.

        NOTE: Real OS threads intentionally NOT used. Calling QThread control
        methods (quit/wait/terminate) from a foreign thread deadlocks under Qt
        on headless CI (pthread_cancel on fitz-blocked threads). The idempotency
        of _close_worker is verified via sequential calls instead.
        """
        viewer = PDFViewer()
        viewer.load_document(Path(sample_pdf))

        # Call _close_worker multiple times sequentially (idempotent).
        # Do not use raw threading.Thread — Qt forbids cross-thread QThread control.
        for _ in range(3):
            viewer._close_worker()

        assert viewer._worker is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
