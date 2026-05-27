from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
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


class _Worker(QObject):
    """Worker generico per eseguire un'operazione core su un QThread."""

    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            if isinstance(result, Path):
                self.finished.emit(result)
            elif isinstance(result, list) and result and isinstance(result[0], Path):
                self.finished.emit(result[0])
            else:
                self.finished.emit(Path())
        except PDFusionError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Errore inatteso: {exc}")


class BasePanelWidget(QWidget):
    """
    Classe base per tutti i pannelli strumento di PDFusion.

    Le sottoclassi devono:
    1. Chiamare super().__init__() con il titolo
    2. Aggiungere widget a self._content_layout
    3. Implementare _collect_config() → config o None
    4. Implementare _run_core(input_path, output_path, password, config) → Path

    Segnali:
        operation_done(Path): emesso quando l'operazione termina con successo.
        status_message(str): messaggio di stato per la status bar.
        preview_requested(Path): emesso quando l'utente richiede l'anteprima;
            il percorso punta a un file temporaneo (non deve essere salvato).
    """

    operation_done = pyqtSignal(Path)
    status_message = pyqtSignal(str)
    preview_requested = pyqtSignal(Path)  # ← nuovo: anteprima nel viewer

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolPanel")
        self._current_path: Path | None = None
        self._current_password: str = ""
        self._thread: QThread | None = None
        self._worker: _Worker | None = None  # ← mantiene il riferimento vivo
        self._preview_thread: QThread | None = None
        self._preview_worker: _Worker | None = None
        self._preview_tmp: Path | None = (
            None  # temp corrente: tracciato dal momento della creazione
        )
        self._original_stem: str = ""  # stem del file originale per il dialogo di salvataggio
        self._supports_preview: bool = True  # le sottoclassi possono disabilitarlo
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
        self._current_path = path
        self._current_password = password
        # Aggiorna _original_stem solo con file "reali":
        # - None → resetta (documento chiuso)
        # - file temp di anteprima → conserva lo stem precedente (chaining)
        # - file normale → usa il suo stem
        if path is None:
            self._original_stem = ""
        elif not path.name.startswith(".pdfusion_preview_"):
            self._original_stem = path.stem
        # se è un temp preview, _original_stem rimane invariato
        self._apply_btn.setEnabled(path is not None)
        self._preview_btn.setEnabled(path is not None and self._supports_preview)
        self._on_file_changed(path)

    def set_current_page(self, page_idx: int) -> None:
        pass

    def reset(self) -> None:
        """
        Ripristina il pannello ai valori di default.
        Chiamato da MainWindow quando si apre o si chiude un documento.
        """
        self._discard_preview_tmp()  # elimina subito eventuali temp in volo
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

    def _collect_config(self):
        return None

    def _run_core(self, input_path: Path, output_path: Path, password: str, config) -> Path:
        raise NotImplementedError

    def _on_file_changed(self, path: Path | None) -> None:
        pass

    # ------------------------------------------------------------------
    # Anteprima
    # ------------------------------------------------------------------

    def _on_preview(self) -> None:
        """Genera il risultato su un file temporaneo e lo mostra nel viewer."""
        if not self._current_path:
            return
        config = self._collect_config()
        if config is None:
            return

        # Crea un file temp nella stessa cartella per compatibilità su Windows.
        # Lo registriamo subito in _preview_tmp: in caso di errore del worker
        # (o file vuoto) siamo noi a eliminarlo, non aspettiamo MainWindow.
        tmp_dir = self._current_path.parent
        tmp_fd, tmp_str = tempfile.mkstemp(suffix=".pdf", prefix=".pdfusion_preview_", dir=tmp_dir)
        import os

        os.close(tmp_fd)
        self._preview_tmp = Path(tmp_str)
        tmp_path = self._preview_tmp

        self._set_busy(True, label="Generazione anteprima…")

        self._preview_thread = QThread(self)
        self._preview_worker = _Worker(
            self._run_core,
            self._current_path,
            tmp_path,
            self._current_password,
            config,
        )
        self._preview_worker.moveToThread(self._preview_thread)
        self._preview_thread.started.connect(self._preview_worker.run)
        self._preview_worker.finished.connect(self._on_preview_done)
        self._preview_worker.error.connect(self._on_error)
        self._preview_worker.finished.connect(self._preview_thread.quit)
        self._preview_worker.error.connect(self._preview_thread.quit)
        self._preview_thread.start()

    @pyqtSlot(Path)
    def _on_preview_done(self, tmp_path: Path) -> None:
        self._set_busy(False)
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            # Guardia contro segnali residui in coda Qt dopo la cancellazione:
            # _discard_preview_tmp() imposta _preview_tmp = None e ferma il thread,
            # ma il segnale "finished" già accodato nella coda del main thread viene
            # comunque consegnato da Qt in un ciclo successivo dell'event loop.
            # Se _preview_tmp è già None qui, os.replace() ha ricreato il file
            # DOPO che l'avevamo cancellato (timeout thread.wait): eliminiamolo e
            # usciamo senza emettere preview_requested.
            if self._preview_tmp is None:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
                return
            # Successo: la proprietà del file passa a MainWindow tramite il segnale.
            self._preview_tmp = None
            self.preview_requested.emit(tmp_path)
            self.status_message.emit(
                "Anteprima generata — il file originale non è stato modificato."
            )
        else:
            # File vuoto o assente: il pannello lo elimina subito (non arriverà mai a MainWindow).
            self._discard_preview_tmp()
            self.status_message.emit("Anteprima non disponibile per questa operazione.")

    # ------------------------------------------------------------------
    # Operazione definitiva
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        if not self._current_path:
            return

        config = self._collect_config()
        if config is None:
            return

        # Cattura sorgente e password PRIMA di aprire il dialogo di salvataggio.
        # Il dialogo esegue un event loop interno: segnali Qt (es. render worker,
        # preview completato su un altro pannello) potrebbero aggiornare
        # _current_path nel frattempo. La cattura preventiva garantisce che
        # l'operazione usi sempre il file sorgente corretto (incluso il preview
        # temp se è attivo, assicurando il chaining corretto tra operazioni).
        source_path = self._current_path
        source_password = self._current_password

        output_path = self._ask_save_path()
        if not output_path:
            return

        self._set_busy(True)

        self._thread = QThread(self)
        self._worker = _Worker(
            self._run_core,
            source_path,
            output_path,
            source_password,
            config,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    @pyqtSlot(Path)
    def _on_done(self, output_path: Path) -> None:
        self._set_busy(False)
        self.operation_done.emit(output_path)

    @pyqtSlot(str)
    def _on_error(self, msg: str) -> None:
        self._set_busy(False)
        # Se l'errore viene dal worker di anteprima, elimina il file temp orfano.
        # Se viene dal worker di apply, _preview_tmp è None e il metodo è no-op.
        self._discard_preview_tmp()
        QMessageBox.critical(self, "Errore", msg)
        self.status_message.emit(f"Errore: {msg}")

    def _discard_preview_tmp(self) -> None:
        """
        Ferma il worker di anteprima (se in esecuzione) e cancella il file temporaneo.

        L'ordine è critico su Windows:
          1. ferma il thread e aspetta che _run_core() completi
             → os.replace(inner_tmp, preview_tmp) ha già trasferito il contenuto
               oppure il thread è uscito prima di arrivarci
          2. solo ora tenta unlink(): il file è in uno stato stabile
             (non può essere ricreato da un os.replace() futuro perché il thread
              è fermo)

        Senza questo attesa, _discard_preview_tmp() elimina il file vuoto creato
        da mkstemp mentre il worker scrive ancora su un inner-temp; poi os.replace()
        lo ricrea → file orfano permanente.
        """
        try:
            # 1. Ferma il thread worker (se in esecuzione).
            #    thread.wait() ritorna solo dopo che run() ha completato, quindi
            #    os.replace() è già avvenuto (o non avverrà mai).
            if self._preview_thread and self._preview_thread.isRunning():
                logger.debug(f"Arresto thread preview del pannello {self.__class__.__name__}...")
                self._preview_thread.quit()
                # Attendi fino a 3 secondi il completamento graceful
                if not self._preview_thread.wait(3000):
                    # Timeout: il worker è bloccato, forzane la terminazione
                    logger.warning(
                        f"Preview thread {self.__class__.__name__} non risponde al quit(), "
                        "forzamento terminazione"
                    )
                    self._preview_thread.terminate()
                    self._preview_thread.wait(1000)  # Attendi la terminazione forzata
                logger.debug(f"Thread preview {self.__class__.__name__} fermato")

            # 2. Il file è ora in uno stato definitivo: unlink() funziona su Windows.
            if self._preview_tmp:
                if self._preview_tmp.exists():
                    try:
                        logger.debug(f"Cancellazione file temporaneo preview: {self._preview_tmp}")
                        self._preview_tmp.unlink()
                    except OSError as e:
                        logger.warning(f"Errore cancellazione temp preview: {e}")
                self._preview_tmp = None

            self._preview_thread = None
            self._preview_worker = None
            logger.debug(f"Discard preview completato per {self.__class__.__name__}")
        except Exception as e:
            logger.error(f"Errore in _discard_preview_tmp ({self.__class__.__name__}): {e}", exc_info=True)

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
