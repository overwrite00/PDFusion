from __future__ import annotations

import logging
from pathlib import Path

import fitz
from PyQt6.QtCore import (
    Q_ARG,
    QMetaObject,
    QObject,
    Qt,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

THUMB_WIDTH = 90
THUMB_HEIGHT = 120
THUMB_DPI = 36  # bassa risoluzione per velocità


# ---------------------------------------------------------------------------
# Worker per il rendering lazy dei thumbnail
# ---------------------------------------------------------------------------


class _ThumbWorker(QObject):
    thumbnail_ready = pyqtSignal(int, QPixmap)  # (page_index, pixmap)

    def __init__(self, doc_path: str, password: str = "") -> None:
        super().__init__()
        self._path = doc_path
        self._password = password
        self._doc: fitz.Document | None = None
        self._closed = False  # impedisce riapertura dopo close()

    @pyqtSlot(int)
    def render(self, page_idx: int) -> None:
        try:
            if self._doc is None:
                if self._closed:
                    return  # close() già chiamato: non riaprire
                self._doc = fitz.open(self._path)
                if self._password:
                    self._doc.authenticate(self._password)
            if page_idx < 0 or page_idx >= self._doc.page_count:
                return
            page = self._doc[page_idx]
            zoom = THUMB_DPI / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            img = QImage(
                pixmap.samples,
                pixmap.width,
                pixmap.height,
                pixmap.stride,
                QImage.Format.Format_RGB888,
            )
            qpix = QPixmap.fromImage(img).scaled(
                THUMB_WIDTH,
                THUMB_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumbnail_ready.emit(page_idx, qpix)
        except Exception:
            pass

    def close(self) -> None:
        """Impedisce nuove aperture. Il documento fitz viene chiuso da
        _close_worker() DOPO thread.wait() per evitare la race condition
        con render() in esecuzione sul thread worker."""
        self._closed = True


# ---------------------------------------------------------------------------
# ThumbnailPanel
# ---------------------------------------------------------------------------


logger = logging.getLogger(__name__)


class ThumbnailPanel(QWidget):
    """
    Striscia di thumbnail con lazy rendering su QThread.
    Supporta drag-drop per il riordino delle pagine.

    Segnali:
        page_clicked(int): indice 0-based della pagina cliccata.
        order_changed(list[int]): nuovo ordine di indici 0-based dopo un drag-drop.
    """

    page_clicked = pyqtSignal(int)
    order_changed = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._total_pages = 0
        self._rendered: set[int] = set()
        # Un QThread nuovo per ogni documento, distrutto in _close_worker():
        # riusare lo stesso QThread tra cicli load/close ripetuti causa crash
        # nativi (worker con thread-affinity stantia accumulati sullo stesso
        # thread riavviato).
        self._thread: QThread | None = None
        self._worker: _ThumbWorker | None = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QListWidget(self)
        self._list.setObjectName("thumbnailPanel")
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(
            __import__("PyQt6.QtCore", fromlist=["QSize"]).QSize(THUMB_WIDTH, THUMB_HEIGHT)
        )
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setMovement(QListWidget.Movement.Snap)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setFixedHeight(THUMB_HEIGHT + 36)
        self._list.setFlow(QListWidget.Flow.LeftToRight)
        self._list.setWrapping(False)
        self._list.setSpacing(4)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_document(self, path: Path, total_pages: int, password: str = "") -> None:
        self._close_worker()
        self._total_pages = total_pages
        self._rendered = set()
        self._list.clear()

        # Aggiungi placeholder per ogni pagina
        for i in range(total_pages):
            item = QListWidgetItem(f"{i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setSizeHint(
                __import__("PyQt6.QtCore", fromlist=["QSize"]).QSize(
                    THUMB_WIDTH + 8, THUMB_HEIGHT + 20
                )
            )
            self._list.addItem(item)

        self._thread = QThread(self)
        self._worker = _ThumbWorker(str(path), password)
        self._worker.moveToThread(self._thread)
        self._worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thread.start()

        # Renderizza le prime 10 thumbnail subito
        for i in range(min(10, total_pages)):
            self._request_thumb(i)

    def set_current_page(self, page_idx: int) -> None:
        if 0 <= page_idx < self._list.count():
            self._list.setCurrentRow(page_idx)
            self._list.scrollToItem(
                self._list.item(page_idx),
                QAbstractItemView.ScrollHint.EnsureVisible,
            )
            self._request_thumb(page_idx)

    def close_document(self) -> None:
        self._close_worker()
        self._list.clear()
        self._total_pages = 0
        self._rendered = set()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _request_thumb(self, page_idx: int) -> None:
        if page_idx in self._rendered or self._worker is None:
            return
        QMetaObject.invokeMethod(
            self._worker,
            "render",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(int, page_idx),
        )

    @pyqtSlot(int, QPixmap)
    def _on_thumbnail_ready(self, page_idx: int, pixmap: QPixmap) -> None:
        self._rendered.add(page_idx)
        item = self._list.item(page_idx)
        if item:
            from PyQt6.QtGui import QIcon

            item.setIcon(QIcon(pixmap))

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self.page_clicked.emit(row)
            self._request_thumb(row)

    def _on_rows_moved(self, *_) -> None:
        new_order = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self._list.count())
        ]
        self.order_changed.emit(new_order)

    def _close_worker(self) -> None:
        # CRITICAL FIX: Snapshot self._worker e self._thread PRIMA di qualsiasi
        # operazione asincrona, per evitare use-after-free se un callback di
        # signal li azzera durante la chiusura.
        worker_snapshot = self._worker
        thread_snapshot = self._thread
        self._worker = None
        self._thread = None

        if worker_snapshot is None:
            logger.debug("Worker thumbnail già chiuso o non inizializzato")
            return

        try:
            # 1. Impedisci nuove chiamate render() sul worker.
            logger.debug("Chiusura worker thumbnail (impostazione flag _closed)")
            worker_snapshot.close()  # sets _closed = True (doesn't touch _doc)
            logger.debug("Worker thumbnail in chiusura...")
        except Exception as e:
            logger.error(f"Errore durante chiusura worker thumbnail: {e}", exc_info=True)
        finally:
            # Garantisce SEMPRE l'arresto del thread e la distruzione di worker
            # e thread, anche se uno step precedente ha sollevato. Un QThread
            # lasciato running e raccolto dal GC fa abortire Qt.
            self._shutdown_thread(thread_snapshot)

            # Chiudi il documento fitz: il thread è ormai fermo.
            if worker_snapshot._doc:
                logger.debug("Chiusura documento fitz in thumbnail...")
                try:
                    worker_snapshot._doc.close()
                except Exception as e:
                    logger.warning(f"Errore chiusura documento fitz thumbnail: {e}")
                finally:
                    worker_snapshot._doc = None

            # Distruggi worker e thread in modo sicuro tramite il loop Qt.
            worker_snapshot.deleteLater()
            if thread_snapshot is not None:
                thread_snapshot.deleteLater()
            logger.debug("Worker thumbnail chiuso correttamente")

    @staticmethod
    def _shutdown_thread(thread: QThread | None) -> None:
        """Ferma un QThread con timeout robusto e niente deadlock.

        CRITICAL FIX: Never use pthread_cancel (terminate()) on Linux/macOS
        when thread may be blocked in fitz.get_pixmap(). The cancel remains
        pending inside non-cancel-safe C code, causing permanent deadlock.
        On Linux/macOS: use only quit() + polling wait().
        On Windows: terminate() is safe as fallback.
        """
        import sys

        if thread is None:
            return
        try:
            if not thread.isRunning():
                return
        except RuntimeError:
            # Thread è stato garbage collected
            return
        logger.debug("Arresto thread thumbnail...")
        # quit() può sollevare (es. mockato nei test, o stato Qt anomalo): se
        # accade dobbiamo comunque tentare l'arresto cooperativo, mai lasciare
        # il thread running (verrebbe distrutto running -> SIGABRT).
        try:
            thread.quit()
        except Exception as e:
            logger.warning(f"quit() del thread thumbnail fallito: {e}")
        try:
            # wait() con timeout breve (100ms polling) in caso di deadlock
            for _ in range(20):  # 20 * 100ms = 2 secondi
                if thread.wait(100):
                    logger.debug("Thread thumbnail fermato da quit()")
                    return
                try:
                    if not thread.isRunning():
                        return
                except RuntimeError:
                    return
        except Exception as e:
            logger.warning(f"wait() del thread thumbnail fallito: {e}")

        # CRITICAL: Do NOT use terminate() on Linux/macOS - causes permanent deadlock
        if sys.platform in ("linux", "darwin"):
            logger.warning(
                "Thread did not stop via quit() on Linux/macOS. "
                "Not using terminate() due to pthread_cancel deadlock risk with fitz. "
                "Relying on job timeout to clean up."
            )
            return

        # On Windows: terminate() is safe as fallback
        try:
            if thread.isRunning():
                logger.warning("Thread thumbnail non fermato dal quit(), forzamento terminazione (Windows)")
                thread.terminate()
                # wait() con timeout breve (100ms polling)
                for _ in range(10):  # 10 * 100ms = 1 secondo
                    if thread.wait(100):
                        logger.debug("Thread thumbnail terminato da terminate()")
                        return
        except Exception as e:
            logger.warning(f"Errore durante terminate() del thread thumbnail: {e}")
        logger.debug("Thread thumbnail fermato")
