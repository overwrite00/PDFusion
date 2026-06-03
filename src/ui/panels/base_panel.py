from __future__ import annotations

import logging
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.panels.config_collector import ConfigCollector
from ui.panels.file_monitor import FileMonitorManager
from ui.panels.preview_renderer import PreviewRenderer
from utils.exceptions import PDFusionError

logger = logging.getLogger(__name__)


def _clear_layout(layout) -> None:
    """Rimuove ricorsivamente tutti i widget e sub-layout da un layout Qt."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        else:
            child = item.layout()
            if child is not None:
                _clear_layout(child)




class BasePanelWidget(QWidget, ConfigCollector):
    """
    Classe base per tutti i pannelli strumento di PDFusion.

    Orchestrates:
    - FileMonitorManager: detects file changes
    - PreviewRenderer: handles preview rendering and thread lifecycle
    - ConfigCollector: gathers and validates user configuration

    Le sottoclassi devono:
    1. Chiamare super().__init__() con il titolo
    2. Aggiungere widget a self._content_layout
    3. Implementare _collect_config_impl() → config o None
    4. Implementare _run_core(input_path, output_path, password, config) → Path

    Segnali:
        operation_done(Path): emesso quando l'operazione termina con successo.
        status_message(str): messaggio di stato per la status bar.
        preview_requested(Path): emesso quando l'utente richiede l'anteprima;
            il percorso punta a un file temporaneo (non deve essere salvato).
    """

    operation_done = pyqtSignal(Path)
    status_message = pyqtSignal(str)
    preview_requested = pyqtSignal(Path)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolPanel")
        self._current_path: Path | None = None
        self._current_password: str = ""
        self._original_stem: str = ""
        self._supports_preview: bool = True

        # Initialize components
        self._file_monitor = FileMonitorManager(self)
        self._file_monitor.file_changed.connect(self._on_file_monitored_changed)

        self._preview_renderer = PreviewRenderer(self)
        self._preview_renderer.preview_ready.connect(self._on_preview_ready)
        self._preview_renderer.preview_failed.connect(self._on_preview_failed)

        self._setup_ui(title)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self, title: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header colorato con titolo
        header = QWidget(self)
        header.setObjectName("panelHeader")
        header.setFixedHeight(44)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        title_label = QLabel(title, header)
        title_label.setObjectName("panelTitle")
        header_layout.addWidget(title_label)
        outer.addWidget(header)

        # Area scroll per il contenuto specifico
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content_widget = QWidget(scroll)
        scroll.setWidget(content_widget)

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(10)
        main_layout.addLayout(self._content_layout)
        main_layout.addStretch()

        # Separatore
        sep = QFrame(content_widget)
        sep.setObjectName("panelSeparator")
        sep.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep)

        # Barra di progresso (nascosta di default)
        self._progress_bar = QProgressBar(content_widget)
        self._progress_bar.setRange(0, 0)  # indeterminata
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        main_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("", content_widget)
        self._status_label.setObjectName("hintLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        main_layout.addWidget(self._status_label)

        # Riga pulsanti: Anteprima | Applica e salva come…
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._preview_btn = QPushButton("Anteprima", content_widget)
        self._preview_btn.setObjectName("previewButton")
        self._preview_btn.setToolTip("Mostra il risultato nel viewer senza salvare il file")
        self._preview_btn.clicked.connect(self._on_preview)
        self._preview_btn.setMinimumHeight(36)
        self._preview_btn.setEnabled(False)
        btn_row.addWidget(self._preview_btn)

        self._apply_btn = QPushButton("Applica e salva come…", content_widget)
        self._apply_btn.setObjectName("applyButton")
        self._apply_btn.clicked.connect(self._on_apply)
        self._apply_btn.setMinimumHeight(36)
        self._apply_btn.setEnabled(False)
        btn_row.addWidget(self._apply_btn)

        main_layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_current_file(self, path: Path | None, password: str = "") -> None:
        # IMPORTANTE: Non aggiornare _current_path se è una preview temporanea.
        # Questo previene l'accumulo di watermark/effetti nelle preview multiple:
        # - Preview 1: applica effetto al file originale → .pdfusion_preview_1
        # - Preview 2: deve partire dal file originale, NON da .pdfusion_preview_1
        # Se aggiornassimo _current_path, la preview 2 applicherebbe l'effetto sopra
        # al risultato della preview 1, creando duplicazione.

        is_preview = path is not None and path.name.startswith(".pdfusion_preview_")

        if path is None:
            # Documento chiuso
            self._current_path = None
            self._current_password = ""
            self._original_stem = ""
        elif not is_preview:
            # È un file reale - aggiorna tracciamento completo
            self._current_path = path
            self._current_password = password
            self._original_stem = path.stem
        # else: È una preview - NON aggiornare _current_path
        # Mantieni il file originale come riferimento per le preview successive

        # Aggiorna UI basato sul file REALE (_current_path), non sulla preview
        # Così i bottoni rimangono correttamente abilitati/disabilitati
        self._apply_btn.setEnabled(self._current_path is not None)
        self._preview_btn.setEnabled(
            self._current_path is not None and self._supports_preview
        )

        # Notifica hook solo per file reali, non per preview temporanee
        if not is_preview:
            self._on_file_changed(self._current_path)

    def set_current_page(self, page_idx: int) -> None:
        pass

    def reset(self) -> None:
        """
        Ripristina il pannello ai valori di default.
        Chiamato da MainWindow quando si apre o si chiude un documento.
        """
        self._preview_renderer.cancel_render()  # cancella eventuali preview in volo
        self._reset_state()  # hook: resetta variabili interne
        _clear_layout(self._content_layout)  # rimuove tutti i widget del form
        self._setup_content()  # ricrea il form con i valori di default

    def _reset_state(self) -> None:
        """
        Hook da sovrascrivere nelle sottoclassi per resettare variabili
        di stato interne (es. _cover_image_path, _files, ecc.).
        Il metodo base non fa nulla.
        """
        pass

    # ------------------------------------------------------------------
    # Da implementare nelle sottoclassi
    # ------------------------------------------------------------------

    def _collect_config_impl(self):
        """ConfigCollector interface: subclasses implement this to collect config."""
        return None

    def _run_core(self, input_path: Path, output_path: Path, password: str, config) -> Path:
        """Subclasses implement the actual PDF operation here."""
        raise NotImplementedError

    def _on_file_changed(self, path: Path | None) -> None:
        """Hook: called when a monitored file changes."""
        pass

    # ------------------------------------------------------------------
    # Anteprima
    # ------------------------------------------------------------------

    def _on_preview(self) -> None:
        """Genera il risultato su un file temporaneo e lo mostra nel viewer."""
        if not self._current_path:
            return

        config = self.collect_config()
        if config is None:
            return

        self._set_busy(True, label="Generazione anteprima…")

        tmp_path = self._preview_renderer.render_preview(
            self._run_core,
            self._current_path,
            config,
            self._current_password,
        )

    @pyqtSlot(Path)
    def _on_preview_ready(self, preview_path: Path) -> None:
        """Called when preview is ready."""
        self._set_busy(False)
        self.preview_requested.emit(preview_path)
        self.status_message.emit(
            "Anteprima generata — il file originale non è stato modificato."
        )

    @pyqtSlot(str)
    def _on_preview_failed(self, error_msg: str) -> None:
        """Called when preview generation fails."""
        self._set_busy(False)
        self.status_message.emit(error_msg)

    # ------------------------------------------------------------------
    # Operazione definitiva
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        if not self._current_path:
            return

        config = self.collect_config()
        if config is None:
            return

        # Cattura sorgente e password PRIMA di aprire il dialogo di salvataggio.
        # Il dialogo esegue un event loop interno: segnali Qt (es. render worker,
        # preview completato su un altro pannello) potrebbero aggiornare
        # _current_path nel frattempo. La cattura preventiva garantisce che
        # l'operazione usi sempre il file sorgente corretto.
        source_path = self._current_path
        source_password = self._current_password

        output_path = self._ask_save_path()
        if not output_path:
            return

        self._set_busy(True)
        self._run_operation(source_path, output_path, source_password, config)

    def _run_operation(self, source_path: Path, output_path: Path, password: str, config) -> None:
        """Run the main PDF operation in a background thread."""
        def _worker_run():
            try:
                result = self._run_core(source_path, output_path, password, config)
                if isinstance(result, Path):
                    self._on_done(result)
                elif isinstance(result, list) and result and isinstance(result[0], Path):
                    self._on_done(result[0])
                else:
                    self._on_done(output_path)
            except PDFusionError as exc:
                self._on_error(str(exc))
            except Exception as exc:
                self._on_error(f"Errore inatteso: {exc}")

        thread = threading.Thread(target=_worker_run, daemon=True)
        thread.start()

    @pyqtSlot(Path)
    def _on_done(self, output_path: Path) -> None:
        self._set_busy(False)
        self.operation_done.emit(output_path)

    def cleanup_preview(self) -> None:
        """Public method to cleanup preview rendering and resources."""
        self._file_monitor.clear_watches()
        self._preview_renderer.cancel_render()

    @pyqtSlot(str)
    def _on_error(self, msg: str) -> None:
        self._set_busy(False)
        self._preview_renderer.cancel_render()
        QMessageBox.critical(self, "Errore", msg)
        self.status_message.emit(f"Errore: {msg}")

    def _on_file_monitored_changed(self, path: Path) -> None:
        """Called by FileMonitorManager when a monitored file changes."""
        # Hook for subclasses to react to file changes
        self._on_file_changed(path)

    def _set_busy(self, busy: bool, label: str = "Elaborazione in corso…") -> None:
        self._apply_btn.setEnabled(not busy)
        self._preview_btn.setEnabled(
            not busy and self._current_path is not None and self._supports_preview
        )
        self._progress_bar.setVisible(busy)
        self._status_label.setVisible(busy)
        if busy:
            self._status_label.setText(label)
            self.status_message.emit(label)
        else:
            self._status_label.setText("")

    def _ask_save_path(self) -> Path | None:
        # Usa il nome del file originale aperto dall'utente, non quello del temp
        # di anteprima (es. ".pdfusion_preview_xyz") che sarebbe fuorviante.
        stem = self._original_stem or (
            self._current_path.stem if self._current_path else "documento"  # type: ignore[union-attr]
        )
        suggested = self._current_path.parent / (stem + "_output.pdf")  # type: ignore[union-attr]
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva PDF come…",
            str(suggested),
            "File PDF (*.pdf)",
        )
        if not path:
            return None
        p = Path(path)
        if p.suffix.lower() != ".pdf":
            p = p.with_suffix(".pdf")
        return p
