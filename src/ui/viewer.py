from __future__ import annotations

import logging
from pathlib import Path

import fitz
from PyQt6.QtCore import QMetaObject, QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QKeyEvent, QPixmap, QWheelEvent
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Worker: renderizza una pagina su un thread separato
# ---------------------------------------------------------------------------


class _RenderWorker(QObject):
    rendered = pyqtSignal(int, QPixmap)  # (page_index, pixmap)
    error = pyqtSignal(str)

    def __init__(self, doc_path: str, password: str = "") -> None:
        super().__init__()
        self._path = doc_path
        self._password = password
        self._doc: fitz.Document | None = None
        self._closed = False  # impedisce riapertura dopo close()

    @pyqtSlot(int, float)
    def render(self, page_idx: int, zoom: float) -> None:
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

    @pyqtSlot()
    def _close_doc(self) -> None:
        """CRITICAL FIX (Ubuntu SIGABRT): Close the fitz document on the
        worker thread BEFORE stopping the thread. This prevents cross-thread
        finalization of fitz C-level resources that corrupts Python's
        condition variable state on Linux's offscreen plugin. Called via
        invokeMethod(BlockingQueuedConnection) from the main thread in
        _close_worker(), ensuring it runs synchronously on the worker thread."""
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass  # Best effort; we'll set _doc = None anyway
            finally:
                self._doc = None


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

        self._doc_path: str | None = None
        self._password: str = ""
        self._total_pages: int = 0
        self._current_page: int = 0
        self._zoom_idx: int = DEFAULT_ZOOM_INDEX

        # Il thread di rendering viene creato per ogni documento e distrutto
        # in _close_worker(): riusare lo stesso QThread tra cicli di
        # load/close ripetuti causa crash nativi (worker con thread-affinity
        # stantia che si accumulano sullo stesso thread riavviato).
        self._thread: QThread | None = None
        self._worker: _RenderWorker | None = None

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
        self._zoom_btn.setToolTip(
            "Clicca per scegliere uno zoom preset\nCtrl + Rotella per zoom continuo"
        )
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
        _title.setStyleSheet("font-size: 16px; font-weight: 600; color: #6B7280; margin-top: 12px;")
        empty_layout.addWidget(_title)

        _hint = QLabel(
            "Apri un PDF dal menu File → Apri…\noppure trascinalo direttamente sulla finestra",
            self._empty_widget,
        )
        _hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _hint.setStyleSheet("font-size: 12px; color: #B0AEA7; margin-top: 6px;")
        _hint.setWordWrap(True)
        empty_layout.addWidget(_hint)

        layout.addWidget(self._empty_widget)

        # Area scroll per la pagina (nascosta finché non si apre un PDF)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(False)  # ← False: rispetta la dimensione nativa del pixmap
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
        # Un QThread nuovo per ogni sessione di rendering (vedi __init__).
        self._thread = QThread(self)
        self._worker = _RenderWorker(self._doc_path, self._password)
        self._worker.moveToThread(self._thread)
        self._worker.rendered.connect(self._on_rendered)
        self._worker.error.connect(self.render_error)
        self._thread.start()

    def _close_worker(self) -> None:
        # CRITICAL FIX: Snapshot self._worker e self._thread PRIMA di qualsiasi
        # operazione asincrona, per evitare use-after-free se un callback di
        # signal li azzera durante la chiusura.
        worker_snapshot = self._worker
        thread_snapshot = self._thread
        self._worker = None
        self._thread = None

        if worker_snapshot is None:
            logger.debug("Worker viewer già chiuso o non inizializzato")
            return

        try:
            # 1. Impedisci nuove chiamate render() sul worker.
            logger.debug("Chiusura worker (impostazione flag _closed)")
            worker_snapshot.close()  # sets _closed = True (doesn't touch _doc)

            # 2. Chiudi il documento fitz dopo aver fermato il thread (vedi
            # finally): qui ci limitiamo a segnalare la chiusura.
            logger.debug("Worker viewer in chiusura...")
        except Exception as e:
            logger.error(f"Errore durante chiusura worker viewer: {e}", exc_info=True)
        finally:
            # CRITICAL FIX (Ubuntu SIGABRT): Close the fitz document ON the worker
            # thread BEFORE stopping it. This prevents cross-thread finalization of
            # fitz resources that corrupts Python's condition variable state on Linux.
            # Use BlockingQueuedConnection to ensure _close_doc runs synchronously on
            # the worker thread before we proceed to quit() + wait().
            if worker_snapshot is not None and thread_snapshot is not None:
                try:
                    if thread_snapshot.isRunning():
                        logger.debug("Chiusura documento fitz sul worker thread...")
                        QMetaObject.invokeMethod(
                            worker_snapshot,
                            "_close_doc",
                            Qt.ConnectionType.BlockingQueuedConnection,
                        )
                except Exception as e:
                    logger.warning(f"Errore chiusura documento fitz via invokeMethod: {e}")
                    # Fallback: close on main thread if invokeMethod fails
                    try:
                        if worker_snapshot._doc:
                            worker_snapshot._doc.close()
                            worker_snapshot._doc = None
                    except Exception as e2:
                        logger.warning(f"Errore fallback chiusura documento: {e2}")

            # Garantisce SEMPRE l'arresto del thread e la distruzione di worker
            # e thread, anche se uno step precedente ha sollevato un'eccezione.
            # Un QThread lasciato in esecuzione e poi raccolto dal GC fa abortire
            # Qt ("QThread: Destroyed while thread is still running").
            self._shutdown_thread(thread_snapshot)

            # Distruggi worker e thread in modo sicuro tramite il loop Qt.
            # deleteLater() è l'approccio corretto in produzione: il worker vive
            # sul thread worker (thread-affinity) e va distrutto dal suo stesso
            # loop eventi, non sincronicamente dal main thread. Nell'app reale il
            # loop eventi elabora DeferredDelete a thread ormai fermo -> sicuro.
            worker_snapshot.deleteLater()
            if thread_snapshot is not None:
                thread_snapshot.deleteLater()
            logger.debug("Worker viewer chiuso correttamente")

    @staticmethod
    def _shutdown_thread(thread: QThread | None) -> None:
        """Ferma un QThread con timeout robusto e niente deadlock.

        CRITICAL FIX: Never use pthread_cancel (terminate()) on Linux with
        headless Qt when the thread may be blocked in fitz.get_pixmap().
        The cancel remains pending inside non-cancel-safe C code, leaving
        the main thread's wait() permanently blocked. Instead, we use only
        cooperative quit() + polling wait() on Linux. On Windows/macOS,
        terminate() is safer as a fallback.
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
        logger.debug("Arresto thread di rendering...")
        # quit() può sollevare (es. mockato nei test, o stato Qt anomalo): se
        # accade dobbiamo comunque tentare l'arresto cooperativo, mai lasciare
        # il thread running (verrebbe distrutto running -> SIGABRT).
        try:
            thread.quit()
        except Exception as e:
            logger.warning(f"quit() del thread fallito: {e}")
        try:
            # ROOT-CAUSE FIX (SIGABRT Ubuntu): usare UN SINGOLO wait() bloccante,
            # NON un polling a 100ms in loop. Sul plugin offscreen di Linux un
            # poll breve riporta spesso "still running" anche se quit() sta per
            # atterrare: il loop si esauriva senza confermare l'arresto, il ramo
            # Linux qui sotto si limitava a loggare, e il thread NON realmente
            # joinato veniva poi distrutto da deleteLater()/~QThread() mentre Qt
            # lo considerava ancora running -> qFatal() -> abort() -> SIGABRT.
            # Un wait() bloccante unico joina davvero il thread (è ciò che ha
            # sempre reso Windows affidabile) e azzera d->running sotto mutex
            # prima del ritorno, rendendo ~QThread() sicuro in ogni piattaforma.
            if thread.wait(5000):
                logger.debug("Thread fermato da quit()")
                return
            try:
                if not thread.isRunning():
                    return
            except RuntimeError:
                return
        except Exception as e:
            logger.warning(f"wait() del thread fallito: {e}")

        # CRITICAL: Do NOT use terminate() on Linux/macOS - causes permanent deadlock
        # when thread is blocked in fitz C code. Both use pthread_cancel which
        # causes the same deadlock. On Windows, terminate() is safer.
        if sys.platform in ("linux", "darwin"):
            # On Linux/macOS headless: quit() is the only safe option.
            # If it didn't work, we accept the thread won't die cleanly.
            # The job timeout-minutes=20 will eventually kill the entire
            # process, preventing infinite hangs.
            logger.warning(
                f"Thread did not stop via quit() on {sys.platform}. "
                "Not using terminate() due to pthread_cancel deadlock risk with fitz. "
                "Relying on job timeout to clean up."
            )
            return

        # On Windows: safe to use terminate() as fallback
        try:
            if thread.isRunning():
                logger.warning("Thread non fermato dal quit(), forzamento terminazione (Windows)")
                thread.terminate()
                # wait() con timeout breve (100ms polling)
                for _ in range(10):  # 10 * 100ms = 1 secondo
                    if thread.wait(100):
                        logger.debug("Thread terminato da terminate()")
                        return
        except Exception as e:
            logger.warning(f"Errore durante terminate() del thread: {e}")
        logger.debug("Thread fermato")

    def _render_current(self) -> None:
        if self._worker is None:
            return
        zoom = ZOOM_LEVELS[self._zoom_idx]
        # Invoca il metodo sul thread worker tramite invokeMethod
        from PyQt6.QtCore import Q_ARG, QMetaObject

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
        chosen = menu.exec(self._zoom_btn.mapToGlobal(self._zoom_btn.rect().bottomLeft()))
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
