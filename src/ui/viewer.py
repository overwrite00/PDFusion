from __future__ import annotations

import logging
from pathlib import Path

import fitz
from PyQt6.QtCore import (
    QMetaObject,
    QMutex,
    QObject,
    Qt,
    QThread,
    QWaitCondition,
    pyqtSignal,
    pyqtSlot,
)
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
        # Sincronizzazione della chiusura documento tra main thread e worker.
        # _close_doc_sync() chiude il doc SUL worker thread e sveglia il main
        # thread, che attende con timeout limitato (vedi _close_worker()).
        self._close_mutex = QMutex()
        self._close_cond = QWaitCondition()
        self._doc_closed = False

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
    def _close_doc_sync(self) -> None:
        """Chiude il documento fitz SUL worker thread e notifica il main thread.

        CRITICAL FIX (Ubuntu SIGABRT): il documento fitz deve essere chiuso sul
        worker thread — MAI sul main thread. La finalizzazione cross-thread delle
        risorse C-level di fitz corrompe lo stato della condition variable di
        Python sul plugin offscreen di Linux e aborta il processo (SIGABRT).

        CRITICAL FIX (Windows/py3.11 deadlock): invece di forzare l'ordinamento
        con BlockingQueuedConnection (che blocca il main thread indefinitamente
        se il worker non è ancora entrato in exec()), questo slot risveglia il
        main thread tramite una QWaitCondition. Il main thread attende con un
        timeout limitato (2s) in _close_worker(): fitz è garantito chiuso sul
        worker thread e il main thread non può mai bloccarsi senza limite.

        Il flag _doc_closed (protetto dal mutex) evita la lost-wakeup race: se
        questo slot gira PRIMA che il main thread chiami wait(), il main vede il
        flag già True e non attende affatto."""
        self._close_mutex.lock()
        try:
            if self._doc is not None:
                try:
                    self._doc.close()
                except Exception:
                    pass  # Best effort; we'll set _doc = None anyway
                finally:
                    self._doc = None
            self._doc_closed = True
            self._close_cond.wakeAll()
        finally:
            self._close_mutex.unlock()


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
            # CRITICAL FIX (Ubuntu SIGABRT + Windows/py3.11 deadlock): chiudi il
            # documento fitz SUL worker thread (mai sul main: la finalizzazione
            # cross-thread di fitz aborta il processo su Linux), e attendi un ACK
            # con timeout LIMITATO. QueuedConnection accoda la chiusura senza
            # bloccare; la QWaitCondition (predicate-guarded) garantisce che fitz
            # sia chiuso PRIMA di fermare il thread, ma con un tetto di 2s che
            # evita il blocco indefinito causato da BlockingQueuedConnection
            # quando l'event loop del worker non è ancora entrato in exec().
            if worker_snapshot is not None and thread_snapshot is not None:
                try:
                    if thread_snapshot.isRunning():
                        logger.debug("Chiusura documento fitz sul worker thread...")
                        worker_snapshot._doc_closed = False
                        invoked = QMetaObject.invokeMethod(
                            worker_snapshot,
                            "_close_doc_sync",
                            Qt.ConnectionType.QueuedConnection,
                        )
                        if not invoked:
                            raise RuntimeError("invokeMethod(_close_doc_sync) ha restituito False")
                        # Attesa bounded dell'ACK dal worker (fitz chiuso sul suo
                        # thread). Il flag protetto dal mutex evita la lost-wakeup
                        # race se il worker ha già chiuso prima di questo wait().
                        worker_snapshot._close_mutex.lock()
                        try:
                            if not worker_snapshot._doc_closed:
                                acked = worker_snapshot._close_cond.wait(
                                    worker_snapshot._close_mutex, 2000
                                )
                                if not acked:
                                    logger.warning(
                                        "Timeout (2s) in attesa della chiusura del "
                                        "documento fitz sul worker thread; proseguo."
                                    )
                        finally:
                            worker_snapshot._close_mutex.unlock()
                except Exception as e:
                    logger.warning(f"Errore chiusura documento fitz via invokeMethod: {e}")
                    # Fallback: close on main thread if the worker hand-off failed.
                    try:
                        if worker_snapshot._doc:
                            worker_snapshot._doc.close()
                            worker_snapshot._doc = None
                    except Exception as e2:
                        logger.warning(f"Errore fallback chiusura documento: {e2}")

            # Ferma il thread. _shutdown_thread ritorna True SOLO se il thread è
            # confermato fermo. Un QThread lasciato in esecuzione e poi distrutto
            # (da deleteLater()/GC) fa abortire Qt con "QThread: Destroyed while
            # thread is still running" -> qFatal() -> abort() -> SIGABRT, un crash
            # C-level che nessun try/except può intercettare.
            thread_stopped = self._shutdown_thread(thread_snapshot)

            # CRITICAL (Ubuntu SIGABRT): pianifica deleteLater() SOLO se il thread
            # è confermato fermo. Se _shutdown_thread NON è riuscito a fermarlo
            # (es. quit() mockato/fallito, o thread bloccato in fitz su Linux dove
            # terminate() è proibito), NON dobbiamo MAI distruggere il thread: la
            # distruzione di un ~QThread() ancora running aborta il processo.
            # Meglio "leakare" l'oggetto orfano (verrà ripulito dalla terminazione
            # del processo / dalla safety net dei test) che far crashare.
            worker_snapshot.deleteLater()
            if thread_snapshot is not None:
                if thread_stopped:
                    thread_snapshot.deleteLater()
                else:
                    logger.warning(
                        "Thread di rendering NON fermato in modo confermato: "
                        "salto deleteLater() per evitare ~QThread() su thread "
                        "vivo (SIGABRT). L'oggetto verrà ripulito più tardi."
                    )
            logger.debug("Worker viewer chiuso correttamente")

    @staticmethod
    def _shutdown_thread(thread: QThread | None) -> bool:
        """Ferma un QThread con timeout robusto e niente deadlock.

        Ritorna ``True`` SOLO se il thread è confermato fermo (o non era mai
        in esecuzione / è già stato distrutto). Ritorna ``False`` se il thread
        è ancora in esecuzione e non è stato possibile fermarlo. Il chiamante
        DEVE usare questo valore per decidere se sia sicuro pianificare
        ``deleteLater()``: distruggere un ``~QThread()`` ancora running chiama
        ``qFatal()`` -> ``abort()`` -> SIGABRT (un segnale C non intercettabile).

        CRITICAL FIX: Never use pthread_cancel (terminate()) on Linux/macOS with
        headless Qt when the thread may be blocked in fitz.get_pixmap().
        The cancel remains pending inside non-cancel-safe C code, leaving
        the main thread's wait() permanently blocked. Instead, we use only
        cooperative quit() + a real blocking wait() on Linux/macOS. On Windows,
        terminate() is safe as a fallback.
        """
        import sys

        if thread is None:
            return True
        try:
            if not thread.isRunning():
                return True
        except RuntimeError:
            # Thread è stato garbage collected
            return True
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
            # atterrare: il loop si esauriva senza confermare l'arresto. Un
            # wait() bloccante unico joina davvero il thread (è ciò che ha
            # sempre reso Windows affidabile) e azzera d->running sotto mutex
            # prima del ritorno, rendendo ~QThread() sicuro in ogni piattaforma.
            if thread.wait(5000):
                logger.debug("Thread fermato da quit()")
                return True
            try:
                if not thread.isRunning():
                    return True
            except RuntimeError:
                return True
        except Exception as e:
            logger.warning(f"wait() del thread fallito: {e}")

        # CRITICAL: Do NOT use terminate() on Linux/macOS - causes permanent deadlock
        # when thread is blocked in fitz C code. Both use pthread_cancel which
        # causes the same deadlock. On Windows, terminate() is safer.
        if sys.platform in ("linux", "darwin"):
            # On Linux/macOS headless: quit() is the only safe option.
            # If it didn't work, we report NOT stopped so the caller skips
            # deleteLater() (destroying a live ~QThread() would SIGABRT).
            logger.warning(
                f"Thread did not stop via quit() on {sys.platform}. "
                "Not using terminate() due to pthread_cancel deadlock risk with fitz. "
                "Reporting not-stopped so deletion is skipped."
            )
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True

        # On Windows: safe to use terminate() as fallback
        try:
            if thread.isRunning():
                logger.warning("Thread non fermato dal quit(), forzamento terminazione (Windows)")
                thread.terminate()
                # wait() con timeout breve (100ms polling)
                for _ in range(10):  # 10 * 100ms = 1 secondo
                    if thread.wait(100):
                        logger.debug("Thread terminato da terminate()")
                        return True
                try:
                    return not thread.isRunning()
                except RuntimeError:
                    return True
        except Exception as e:
            logger.warning(f"Errore durante terminate() del thread: {e}")
            try:
                return not thread.isRunning()
            except RuntimeError:
                return True
        logger.debug("Thread fermato")
        return True

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
