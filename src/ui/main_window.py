from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from ui.sidebar import Sidebar
from ui.thumbnail_panel import ThumbnailPanel
from ui.viewer import PDFViewer
from ui.widgets.recent_files_widget import RecentFilesWidget
from utils.config import APP_NAME, VERSION
from utils.recent_files import add_recent_file


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._current_path: Path | None = None
        self._current_password: str = ""
        self._pending_preview: Path | None = None  # file temp anteprima corrente
        self._temp_files: list[Path] = []  # tutti i temp creati nella sessione

        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self.setAcceptDrops(True)

        self._setup_toolbar()  # deve venire prima di _setup_ui (toolbar_widget usato lì)
        self._setup_ui()
        self._setup_menus()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        from PyQt6.QtWidgets import QVBoxLayout

        # Contenitore principale: toolbar + splitter
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # La toolbar viene creata in _setup_toolbar (chiamato prima) e aggiunta qui
        root_layout.addWidget(self._toolbar_widget)

        # Splitter orizzontale principale
        main_splitter = QSplitter(Qt.Orientation.Horizontal, root)
        main_splitter.setHandleWidth(1)

        # --- Sidebar ---
        self._sidebar = Sidebar(main_splitter)
        main_splitter.addWidget(self._sidebar)

        # --- Centro: viewer + thumbnail ---
        center = QWidget(main_splitter)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._viewer = PDFViewer(center)
        center_layout.addWidget(self._viewer, stretch=1)

        self._thumbnails = ThumbnailPanel(center)
        center_layout.addWidget(self._thumbnails)

        main_splitter.addWidget(center)

        # --- Pannello tool a destra ---
        self._stack = QStackedWidget(main_splitter)
        self._stack.setObjectName("toolPanel")
        self._stack.setMinimumWidth(300)
        self._stack.setMaximumWidth(400)
        main_splitter.addWidget(self._stack)

        main_splitter.setSizes([200, 700, 340])
        root_layout.addWidget(main_splitter)
        self.setCentralWidget(root)

        # Welcome (nessun documento aperto)
        self._welcome = RecentFilesWidget(self._stack)
        self._welcome.file_selected.connect(self.open_file)
        self._stack.addWidget(self._welcome)

        # Carica i pannelli tool
        self._panels: dict[str, QWidget] = {}
        self._load_panels()

        # Status bar
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._set_status("Pronto")

    def _load_panels(self) -> None:
        from ui.panels.batch_panel import BatchPanel
        from ui.panels.compress_panel import CompressPanel
        from ui.panels.delete_panel import DeletePanel
        from ui.panels.export_images_panel import ExportImagesPanel
        from ui.panels.extract_panel import ExtractPanel
        from ui.panels.headers_footers_panel import HeadersFootersPanel
        from ui.panels.import_images_panel import ImportImagesPanel
        from ui.panels.insert_panel import InsertPanel
        from ui.panels.license_panel import LicensePanel
        from ui.panels.merge_panel import MergePanel
        from ui.panels.metadata_panel import MetadataPanel
        from ui.panels.protect_panel import ProtectPanel
        from ui.panels.reorder_panel import ReorderPanel
        from ui.panels.rotate_panel import RotatePanel
        from ui.panels.split_panel import SplitPanel
        from ui.panels.watermark_panel import WatermarkPanel

        panel_classes = {
            "split": SplitPanel,
            "merge": MergePanel,
            "delete_page": DeletePanel,
            "insert_page": InsertPanel,
            "compress": CompressPanel,
            "protect": ProtectPanel,
            "watermark": WatermarkPanel,
            "license_page": LicensePanel,
            "headers_footers": HeadersFootersPanel,
            "rotate": RotatePanel,
            "reorder": ReorderPanel,
            "extract": ExtractPanel,
            "metadata": MetadataPanel,
            "pdf_to_images": ExportImagesPanel,
            "images_to_pdf": ImportImagesPanel,
            "batch": BatchPanel,
        }

        for key, cls in panel_classes.items():
            panel = cls(self)
            panel.operation_done.connect(self._on_operation_done)
            panel.status_message.connect(self._set_status)
            panel.preview_requested.connect(self._on_preview_requested)
            self._stack.addWidget(panel)
            self._panels[key] = panel

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _setup_toolbar(self) -> None:
        """Barra degli strumenti come QWidget personalizzato (più controllo visivo)."""
        tb = QWidget(self)
        tb.setObjectName("appToolbar")
        tb.setFixedHeight(44)
        tb_layout = QHBoxLayout(tb)
        tb_layout.setContentsMargins(10, 0, 10, 0)
        tb_layout.setSpacing(4)

        def _btn(label: str, tip: str) -> QPushButton:
            b = QPushButton(label, tb)
            b.setObjectName("toolbarButton")
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(30)
            return b

        open_btn = _btn("Apri PDF…", "Apri un file PDF  (Ctrl+O)")
        open_btn.clicked.connect(self._on_open)
        # Collega anche la shortcut Ctrl+O tramite QAction nascosta
        open_ka = QAction(self)
        open_ka.setShortcut(QKeySequence.StandardKey.Open)
        open_ka.triggered.connect(self._on_open)
        self.addAction(open_ka)
        tb_layout.addWidget(open_btn)

        # Separatore visivo
        _sep1 = QLabel("|", tb)
        _sep1.setObjectName("toolbarSep")
        tb_layout.addWidget(_sep1)

        self._tb_prev_btn = _btn("← Pagina prec.", "Pagina precedente  (←)")
        self._tb_prev_btn.setEnabled(False)
        self._tb_prev_btn.clicked.connect(lambda: self._viewer.prev_page())
        tb_layout.addWidget(self._tb_prev_btn)

        self._tb_next_btn = _btn("Pagina succ. →", "Pagina successiva  (→)")
        self._tb_next_btn.setEnabled(False)
        self._tb_next_btn.clicked.connect(lambda: self._viewer.next_page())
        tb_layout.addWidget(self._tb_next_btn)

        _sep2 = QLabel("|", tb)
        _sep2.setObjectName("toolbarSep")
        tb_layout.addWidget(_sep2)

        close_btn = _btn("Chiudi documento", "Chiudi il documento corrente  (Ctrl+W)")
        close_btn.clicked.connect(self.close_document)
        close_ka = QAction(self)
        close_ka.setShortcut(QKeySequence("Ctrl+W"))
        close_ka.triggered.connect(self.close_document)
        self.addAction(close_ka)
        tb_layout.addWidget(close_btn)

        tb_layout.addStretch()

        # Inizializzazione degli handle per aggiornare enabled (compatibili con vecchio codice)
        self._tb_prev = None  # QAction non più usate
        self._tb_next = None

        # Aggiungi la toolbar al layout principale sopra il centralWidget
        # Usiamo un wrapper per inserirla come widget fisso sopra lo splitter
        from PyQt6.QtWidgets import QVBoxLayout

        wrapper = QWidget(self)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(tb)
        # Il centralWidget verrà aggiunto dopo in _setup_ui tramite setCentralWidget
        # qui salviamo il widget toolbar per usarlo in _setup_ui
        self._toolbar_widget = tb

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("File")
        open_act = QAction("Apri…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._on_open)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        self._save_act = QAction("Salva con modifiche…", self)
        self._save_act.setShortcut(QKeySequence.StandardKey.Save)
        self._save_act.setEnabled(False)
        self._save_act.triggered.connect(self._on_save)
        file_menu.addAction(self._save_act)

        file_menu.addSeparator()

        close_act = QAction("Chiudi documento", self)
        close_act.setShortcut(QKeySequence("Ctrl+W"))
        close_act.triggered.connect(self.close_document)
        file_menu.addAction(close_act)

        file_menu.addSeparator()

        quit_act = QAction("Esci", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # Help
        help_menu = menubar.addMenu("?")
        about_act = QAction(f"Informazioni su {APP_NAME}", self)
        about_act.triggered.connect(self._on_about)
        help_menu.addAction(about_act)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._sidebar.tool_selected.connect(self._on_tool_selected)
        self._sidebar.quit_requested.connect(self.close)
        self._viewer.page_changed.connect(self._on_viewer_page_changed)
        self._viewer.document_loaded.connect(self._on_document_loaded)
        self._viewer.render_error.connect(self._on_render_error)
        self._thumbnails.page_clicked.connect(self._viewer.go_to_page)
        self._thumbnails.order_changed.connect(self._on_reorder_from_thumbnail)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_file(self, path: Path, password: str = "") -> None:
        if not path.exists():
            QMessageBox.warning(self, "File non trovato", str(path))
            return
        # Chiudi prima viewer e thumbnail: rilasciano gli handle fitz sul file
        # temporaneo corrente. Su Windows i file aperti non si possono eliminare,
        # quindi _cleanup_all_temps() deve girare DOPO la chiusura degli handle.
        self._viewer.close_document()
        self._thumbnails.close_document()
        self._cleanup_all_temps()
        self._current_path = path
        self._current_password = password
        self._reset_panels()  # resetta tutti i pannelli ai valori di default
        self._viewer.load_document(path, password)
        add_recent_file(path)
        self._welcome.refresh()
        self._set_status(f"Aperto: {path.name}")
        self._save_act.setEnabled(True)
        self._update_panels()

    def close_document(self) -> None:
        self._current_path = None
        self._current_password = ""
        # Rilascia prima gli handle fitz, poi elimina i temporanei.
        self._viewer.close_document()
        self._thumbnails.close_document()
        self._cleanup_all_temps()  # elimina tutti i file temporanei della sessione
        self._reset_panels()  # resetta tutti i pannelli ai valori di default
        self._stack.setCurrentWidget(self._welcome)
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self._tb_prev_btn.setEnabled(False)
        self._tb_next_btn.setEnabled(False)
        self._save_act.setEnabled(False)

    def current_path(self) -> Path | None:
        return self._current_path

    def current_password(self) -> str:
        return self._current_password

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Apri PDF", "", "PDF (*.pdf)")
        if path:
            self._on_open_path(Path(path))

    def _on_tool_selected(self, key: str) -> None:
        panel = self._panels.get(key)
        if panel:
            self._stack.setCurrentWidget(panel)
            # Se c'è un'anteprima attiva i pannelli lavorano su di essa,
            # non sul file originale (consente di concatenare le operazioni).
            effective = self._pending_preview or self._current_path
            pwd = "" if self._pending_preview else self._current_password
            panel.set_current_file(effective, pwd)

    def _on_document_loaded(self, total: int) -> None:
        # Se c'è un'anteprima attiva, carica le thumbnail dal file temporaneo
        # (altrimenti verrebbero caricate dall'originale con il conteggio sbagliato)
        if self._pending_preview:
            thumb_path = self._pending_preview
            thumb_pwd = ""
            title_suffix = (
                f"{self._current_path.name} — Anteprima" if self._current_path else "Anteprima"
            )
        else:
            thumb_path = self._current_path
            thumb_pwd = self._current_password
            title_suffix = self._current_path.name if self._current_path else ""

        if thumb_path:
            self._thumbnails.load_document(thumb_path, total, thumb_pwd)

        self.setWindowTitle(f"{APP_NAME} — {title_suffix}")
        self._update_toolbar_nav()

    def _on_viewer_page_changed(self, page_idx: int) -> None:
        self._thumbnails.set_current_page(page_idx)
        self._update_toolbar_nav()
        # Aggiorna il pannello attivo se è "delete_page"
        if isinstance(self._stack.currentWidget(), type(self._panels.get("delete_page"))):
            self._panels["delete_page"].set_current_page(page_idx)  # type: ignore

    def _on_render_error(self, msg: str) -> None:
        self._set_status(f"Errore rendering: {msg}")

    def _on_operation_done(self, output_path: Path) -> None:
        self._set_status(f"Salvato: {output_path.name}")
        # Offre di aprire subito il file risultante nel viewer.
        answer = QMessageBox.question(
            self,
            "Operazione completata",
            f"File salvato:\n{output_path}\n\nVuoi aprirlo ora nel viewer?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.open_file(output_path)  # gestisce cleanup e reset internamente
        else:
            # L'utente non apre il risultato nel viewer, ma aggiorniamo comunque
            # il documento corrente all'output. Questo garantisce il chaining corretto:
            # operazioni successive (es. protect dopo license) useranno l'output
            # come sorgente anziché il file originale.
            #
            # ORDINE CRITICO su Windows:
            # 1. chiudi viewer e thumbnail → rilascia handle fitz sul preview temp
            # 2. elimina i temp (ora liberi da handle)
            # 3. aggiorna _current_path all'output
            # 4. ricarica il viewer con l'output (evita che resti agganciato a file cancellati)
            self._viewer.close_document()
            self._thumbnails.close_document()
            self._cleanup_all_temps()
            self._current_path = output_path
            self._current_password = ""  # password non nota; richiesta se serve
            self._reset_panels()
            self._viewer.load_document(output_path, "")
            add_recent_file(output_path)
            self._welcome.refresh()
            self.setWindowTitle(f"{APP_NAME} — {output_path.name}")
            self._save_act.setEnabled(True)
            self._update_panels()
            self._update_toolbar_nav()

    def _on_reorder_from_thumbnail(self, new_order: list) -> None:
        # Il pannello Reorder applica automaticamente il riordino
        reorder_panel = self._panels.get("reorder")
        if reorder_panel and self._current_path:
            reorder_panel.apply_order(new_order, self._current_path, self._current_password)

    def _update_panels(self) -> None:
        # Se c'è un'anteprima attiva, i pannelli devono lavorare su di essa.
        # Dopo _cleanup_all_temps() _pending_preview è None, quindi si torna
        # automaticamente al file originale senza logica aggiuntiva.
        effective = self._pending_preview or self._current_path
        pwd = "" if self._pending_preview else self._current_password
        for panel in self._panels.values():
            panel.set_current_file(effective, pwd)

    def _reset_panels(self) -> None:
        """Ripristina tutti i pannelli strumento ai valori di default."""
        for panel in self._panels.values():
            panel.reset()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _on_preview_requested(self, tmp_path: Path) -> None:
        """
        Mostra il file temporaneo nel viewer come anteprima.
        Non modifica _current_path: il documento originale rimane invariato.
        Propaga il file di anteprima a tutti i pannelli, così le operazioni
        successive (es. Unisci dopo Licenza) useranno questo file come base,
        permettendo di concatenare più operazioni tramite Anteprima.
        Il segnale document_loaded verrà emesso in modo sincrono durante load_document,
        quindi _pending_preview deve essere impostato PRIMA della chiamata.
        """
        # Guardia contro segnali tardivi: se il file è stato cancellato nel frattempo
        # (es. da _cleanup_all_temps() dopo una operazione), non tentare di caricarlo
        if not tmp_path.exists():
            return

        # ORDINE CRITICO su Windows:
        # 1. chiudi viewer e thumbnail → rilascia l'handle fitz sul temp precedente
        # 2. cancella il temp precedente (ora libero)
        # 3. imposta _pending_preview PRIMA di load_document (document_loaded è sincrono)
        # 4. carica il nuovo temp
        self._viewer.close_document()
        self._thumbnails.close_document()
        self._cleanup_preview()  # il file è ora libero → unlink() funziona
        self._pending_preview = tmp_path  # deve precedere load_document!
        # Registra il nuovo temp nella lista di tracciamento per cleanup completo
        if tmp_path not in self._temp_files:
            self._temp_files.append(tmp_path)
        self._viewer.load_document(tmp_path, "")
        self._set_status(
            "⚠ Anteprima — il file originale NON è stato modificato. "
            "Usa 'Applica e salva come…' per salvare."
        )
        # Propaga il file di anteprima a tutti i pannelli: le operazioni successive
        # (es. merge dopo licenza) useranno questo file come base invece dell'originale.
        # Il file di anteprima non ha password perché è generato internamente.
        for panel in self._panels.values():
            panel.set_current_file(tmp_path, "")

    def _on_save(self) -> None:
        """Ctrl+S — delega al pannello attivo il salvataggio con modifiche."""
        current = self._stack.currentWidget()
        if current and hasattr(current, "_on_apply"):
            current._on_apply()
        elif self._current_path:
            # Nessun pannello attivo: propone copia del file corrente
            from PyQt6.QtWidgets import QFileDialog

            suggested = self._current_path.parent / (self._current_path.stem + "_copia.pdf")
            dest, _ = QFileDialog.getSaveFileName(
                self, "Salva copia come…", str(suggested), "File PDF (*.pdf)"
            )
            if dest:
                import shutil

                shutil.copy2(str(self._current_path), dest)
                self._set_status(f"Copia salvata: {Path(dest).name}")

    def _update_toolbar_nav(self) -> None:
        total = self._viewer.total_pages()
        cur = self._viewer.current_page_index()
        self._tb_prev_btn.setEnabled(total > 0 and cur > 0)
        self._tb_next_btn.setEnabled(total > 0 and cur < total - 1)

    def _on_about(self) -> None:
        from ui.dialogs.about_dialog import AboutDialog

        AboutDialog(self).exec()

    def _set_status(self, msg: str) -> None:
        self._status.showMessage(msg, 5000)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(".pdf") for u in urls):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".pdf" and path.exists():
                self._on_open_path(path)
                break

    def _on_open_path(self, p: Path) -> None:
        import fitz

        doc = fitz.open(str(p))
        try:
            needs_pwd = doc.needs_pass
        finally:
            doc.close()
        password = ""
        if needs_pwd:
            from ui.dialogs.password_dialog import ask_password

            password = ask_password(p.name, self) or ""
            if not password:
                return
        self.open_file(p, password)

    def _cleanup_preview(self) -> None:
        """Elimina il file temporaneo di anteprima corrente (solo quello attivo)."""
        if self._pending_preview:
            deleted = not self._pending_preview.exists()  # già assente = ok
            if not deleted:
                try:
                    self._pending_preview.unlink()
                    deleted = True
                except OSError:
                    pass
            # Rimuove dalla lista di tracciamento SOLO se cancellato con successo.
            # Se la cancellazione fallisce (file ancora bloccato), il path rimane
            # in _temp_files e _cleanup_all_temps() potrà ritentare in seguito.
            if deleted:
                try:
                    self._temp_files.remove(self._pending_preview)
                except ValueError:
                    pass
            self._pending_preview = None

    def _cleanup_all_temps(self) -> None:
        """
        Elimina tutti i file temporanei creati durante la sessione corrente.
        Chiamato alla chiusura documento, all'apertura di un nuovo file,
        dopo il salvataggio (se l'utente non apre il risultato) e alla chiusura app.
        """
        for p in list(self._temp_files):
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        self._temp_files.clear()
        self._pending_preview = None

    def closeEvent(self, event: QCloseEvent) -> None:
        # Ordine critico su Windows:
        # 1. rilascia gli handle fitz del viewer e delle thumbnail
        # 2. elimina i temp in volo nei pannelli (worker di anteprima attivi)
        # 3. elimina tutti i temp tracciati in _temp_files
        self._viewer.close_document()
        self._thumbnails.close_document()
        for panel in self._panels.values():
            panel._discard_preview_tmp()
        self._cleanup_all_temps()
        event.accept()
