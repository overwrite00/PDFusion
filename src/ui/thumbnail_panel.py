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
        self._thread = QThread(self)
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
        try:
            # 1. Segnala al worker di fermarsi
            if self._worker:
                logger.debug("Chiusura worker thumbnail (impostazione flag _closed)")
                self._worker.close()  # imposta _closed = True (non tocca _doc)

            # 2. Ferma il thread
            if self._thread.isRunning():
                logger.debug("Arresto thread thumbnail...")
                self._thread.quit()
                if not self._thread.wait(2000):
                    logger.warning("Thread thumbnail non ha risposto al quit(), forzamento terminazione")
                    self._thread.terminate()
                    self._thread.wait(1000)
                logger.debug("Thread thumbnail fermato")

            # 3. Chiudi documento fitz: il thread è fermo,
            # nessuna esecuzione di render() è più attiva
            if self._worker and self._worker._doc:
                logger.debug("Chiusura documento fitz in thumbnail...")
                try:
                    self._worker._doc.close()
                except Exception as e:
                    logger.warning(f"Errore chiusura documento fitz thumbnail: {e}")
                finally:
                    self._worker._doc = None

            self._worker = None
            logger.debug("Worker thumbnail chiuso correttamente")
        except Exception as e:
            logger.error(f"Errore durante chiusura worker thumbnail: {e}", exc_info=True)
