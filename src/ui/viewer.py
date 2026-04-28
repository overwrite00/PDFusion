from __future__ import annotations

from pathlib import Path
from typing import Optional

import fitz
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QWheelEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Worker: renderizza una pagina su un thread separato
# ---------------------------------------------------------------------------

class _RenderWorker(QObject):
    rendered = pyqtSignal(int, QPixmap)   # (page_index, pixmap)
    error = pyqtSignal(str)

    def __init__(self, doc_path: str, password: str = "") -> None:
        super().__init__()
        self._path = doc_path
        self._password = password
        self._doc: Optional[fitz.Document] = None
        self._closed = False   # impedisce riapertura dopo close()

    @pyqtSlot(int, float)
    def render(self, page_idx: int, zoom: float) -> None:
        try:
            if self._doc is None:
                if self._closed:
                    return   # close() già chiamato: non riaprire
                self._doc = fitz.open(self._path)
                if self._password:
                    self._doc.authenticate(self._password)
            if page_idx < 0 or page_idx >= self._doc.page_count:
                return
            page = self._doc[page_idx]
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            img = QImage(
                pixmap.samples,
                pixmap.width,
                pixmap.height,
                pixmap.stride,
                QImage.Format.Format_RGB888,
            )
            self.rendered.emit(page_idx, QPixmap.fromImage(img))
        except Exception as exc:
            self.error.emit(str(exc))

    def close(self) -> None:
        """Impedisce nuove aperture. Il documento fitz viene chiuso da
        _close_worker() DOPO thread.wait() per evitare la race condition
        con render() in esecuzione sul thread worker (su Windows l'handle
        del file rimane aperto finché il thread non abbandona i riferimenti
        interni, rendendo impossibile unlink() se si chiude qui)."""
        self._closed = True


# ---------------------------------------------------------------------------
# PDFViewer widget
# ---------------------------------------------------------------------------

ZOOM_LEVELS = [0.5, 0.67, 0.75, 0.90, 1.0, 1.25, 1.5, 2.0]
ZOOM_LABELS = ["50%", "67%", "75%", "90%", "100%", "125%", "150%", "200%"]
DEFAULT_ZOOM_INDEX = 4  # 100%


class PDFViewer(QWidget):
    """
    Visualizzatore PDF con navigazione pagine e zoom.

    Segnali:
        page_changed(int): indice 0-based della pagina corrente.
        document_loaded(int): totale pagine dopo apertura.
        render_error(str): messaggio di errore di rendering.
    """

    page_changed = pyqtSignal(int)
    document_loaded = pyqtSignal(int)
    render_error = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("viewerArea")

        self._doc_path: Optional[str] = None
        self._password: str = ""
        self._total_pages: int = 0
        self._current_page: int = 0
        self._zoom_idx: int = DEFAULT_ZOOM_INDEX

        self._thread = QThread(self)
        self._worker: Optional[_RenderWorker] = None

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra di navigazione
        nav = QWidget(self)
        nav.setObjectName("viewerNav")
        nav.setFixedHeight(42)
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(10, 0, 10, 0)
        nav_layout.setSpacing(4)

        self._prev_btn = QPushButton("← Prec.", nav)
        self._prev_btn.setObjectName("navButton")
        self._prev_btn.setToolTip("Pagina precedente  (← / PgSu)")
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(self.prev_page)
        nav_layout.addWidget(self._prev_btn)

        # Campo pagina + totale
        nav_layout.addSpacing(6)
        self._page_edit = QLineEdit(nav)
        self._page_edit.setObjectName("pageEdit")
        self._page_edit.setFixedWidth(44)
        self._page_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_edit.setToolTip("Inserisci il numero di pagina e premi Invio")
        self._page_edit.returnPressed.connect(self._on_page_edit)
        nav_layout.addWidget(self._page_edit)

        self._total_label = QLabel("/ —", nav)
        self._total_label.setObjectName("pageTotalLabel")
        self._total_label.setMinimumWidth(40)
        nav_layout.addWidget(self._total_label)
        nav_layout.addSpacing(6)

        self._next_btn = QPushButton("Succ. →", nav)
        self._next_btn.setObjectName("navButton")
        self._next_btn.setToolTip("Pagina successiva  (→ / PgGiù)")
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self.next_page)
        nav_layout.addWidget(self._next_btn)

        nav_layout.addStretch()

        # ---- Controllo zoom: [−]  [100% ▼]  [+] ----
        zoom_out_btn = QPushButton("−", nav)
        zoom_out_btn.setObjectName("zoomStepButton")
        zoom_out_btn.setToolTip("Riduci zoom  (Ctrl + Rotella ↓)")
        zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.clicked.connect(self._zoom_out)
        nav_layout.addWidget(zoom_out_btn)

        self._zoom_btn = QPushButton(ZOOM_LABELS[DEFAULT_ZOOM_INDEX] + " ▼", nav)
        self._zoom_btn.setObjectName("zoomValueButton")
        self._zoom_btn.setToolTip("Clicca per scegliere uno zoom preset\nCtrl + Rotella per zoom continuo")
        self._zoom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_btn.setFixedSize(82, 28)
        self._zoom_btn.clicked.connect(self._show_zoom_menu)
        nav_layout.addWidget(self._zoom_btn)

        zoom_in_btn = QPushButton("+", nav)
        zoom_in_btn.setObjectName("zoomStepButton")
        zoom_in_btn.setToolTip("Aumenta zoom  (Ctrl + Rotella ↑)")
        zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.clicked.connect(self._zoom_in)
        nav_layout.addWidget(zoom_in_btn)
        nav_layout.addSpacing(4)

        layout.addWidget(nav)

        # Placeholder "nessun documento" — mostrato quando non c'è PDF aperto
        self._empty_widget = QWidget(self)
        self._empty_widget.setObjectName("emptyState")
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        _icon = QLabel("📄", self._empty_widget)
        _icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _icon.setStyleSheet("font-size: 52px; color: #B0AEA7;")
        empty_layout.addWidget(_icon)

        _title = QLabel("Nessun documento aperto", self._empty_widget)
        _title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _title.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #6B7280; margin-top: 12px;"
        )
        empty_layout.addWidget(_title)

        _hint = QLabel(
            "Apri un PDF dal menu File → Apri…\n"
            "oppure trascinalo direttamente sulla finestra",
            self._empty_widget,
        )
        _hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _hint.setStyleSheet("font-size: 12px; color: #B0AEA7; margin-top: 6px;")
        _hint.setWordWrap(True)
        empty_layout.addWidget(_hint)

        layout.addWidget(self._empty_widget)

        # Area scroll per la pagina (nascosta finché non si apre un PDF)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(False)   # ← False: rispetta la dimensione nativa del pixmap
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setVisible(False)

        self._page_label = QLabel()
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidget(self._page_label)
        layout.addWidget(self._scroll)

        self._update_nav_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_document(self, path: Path, password: str = "") -> None:
        self._close_worker()
        self._doc_path = str(path)
        self._password = password

        # Leggi il totale pagine velocemente
        try:
            doc = fitz.open(self._doc_path)
            if password:
                doc.authenticate(password)
            self._total_pages = doc.page_count
            doc.close()
        except Exception as exc:
            self.render_error.emit(str(exc))
            return

        self._current_page = 0
        self._empty_widget.setVisible(False)
        self._scroll.setVisible(True)
        self._start_worker()
        self._render_current()
        self._update_nav_state()
        self.document_loaded.emit(self._total_pages)

    def close_document(self) -> None:
        self._close_worker()
        self._doc_path = None
        self._total_pages = 0
        self._current_page = 0
        self._page_label.clear()
        self._scroll.setVisible(False)
        self._empty_widget.setVisible(True)
        self._update_nav_state()

    def current_page_index(self) -> int:
        """Ritorna l'indice 0-based della pagina corrente."""
        return self._current_page

    def total_pages(self) -> int:
        return self._total_pages

    def go_to_page(self, index: int) -> None:
        if self._total_pages == 0:
            return
        index = max(0, min(index, self._total_pages - 1))
        if index != self._current_page:
            self._current_page = index
            self._render_current()
            self._update_nav_state()
            self.page_changed.emit(self._current_page)

    def reload(self) -> None:
        """Ricarica il documento (utile dopo modifiche al file)."""
        if self._doc_path:
            path = Path(self._doc_path)
            page = self._current_page
            self.load_document(path, self._password)
            self.go_to_page(page)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def prev_page(self) -> None:
        self.go_to_page(self._current_page - 1)

    def next_page(self) -> None:
        self.go_to_page(self._current_page + 1)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self._zoom_in()
            else:
                self._zoom_out()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown):
            self.next_page()
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp):
            self.prev_page()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _start_worker(self) -> None:
        if self._doc_path is None:
            return
        self._worker = _RenderWorker(self._doc_path, self._password)
        self._worker.moveToThread(self._thread)
        self._worker.rendered.connect(self._on_rendered)
        self._worker.error.connect(self.render_error)
        self._thread.start()

    def _close_worker(self) -> None:
        if self._worker:
            self._worker.close()          # imposta _closed = True (non tocca _doc)
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)       # aspetta che il thread finisca
        # Solo ora chiudiamo il documento fitz: il thread è fermo,
        # nessuna esecuzione di render() è più attiva e tutti i riferimenti
        # interni a page/pixmap sono stati abbandonati → handle rilasciato.
        if self._worker and self._worker._doc:
            self._worker._doc.close()
            self._worker._doc = None

    def _render_current(self) -> None:
        if self._worker is None:
            return
        zoom = ZOOM_LEVELS[self._zoom_idx]
        # Invoca il metodo sul thread worker tramite invokeMethod
        from PyQt6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(
            self._worker,
            "render",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(int, self._current_page),
            Q_ARG(float, zoom),
        )

    @pyqtSlot(int, QPixmap)
    def _on_rendered(self, page_idx: int, pixmap: QPixmap) -> None:
        if page_idx == self._current_page:
            self._page_label.setPixmap(pixmap)
            self._page_label.resize(pixmap.size())

    def _zoom_in(self) -> None:
        if self._zoom_idx < len(ZOOM_LEVELS) - 1:
            self._set_zoom(self._zoom_idx + 1)

    def _zoom_out(self) -> None:
        if self._zoom_idx > 0:
            self._set_zoom(self._zoom_idx - 1)

    def _set_zoom(self, index: int) -> None:
        self._zoom_idx = index
        self._zoom_btn.setText(ZOOM_LABELS[index] + " ▼")
        self._render_current()

    def _show_zoom_menu(self) -> None:
        """Mostra un menu popup con i livelli zoom preset."""
        menu = QMenu(self)
        menu.setObjectName("zoomMenu")
        for i, label in enumerate(ZOOM_LABELS):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(i == self._zoom_idx)
            action.setData(i)
        chosen = menu.exec(
            self._zoom_btn.mapToGlobal(
                self._zoom_btn.rect().bottomLeft()
            )
        )
        if chosen is not None:
            self._set_zoom(chosen.data())

    def _on_page_edit(self) -> None:
        try:
            num = int(self._page_edit.text())
            self.go_to_page(num - 1)
        except ValueError:
            self._update_nav_state()

    def _update_nav_state(self) -> None:
        has_doc = self._total_pages > 0
        self._prev_btn.setEnabled(has_doc and self._current_page > 0)
        self._next_btn.setEnabled(has_doc and self._current_page < self._total_pages - 1)

        if has_doc:
            self._page_edit.setText(str(self._current_page + 1))
            self._total_label.setText(f"/ {self._total_pages}")
        else:
            self._page_edit.setText("")
            self._total_label.setText("/ —")
