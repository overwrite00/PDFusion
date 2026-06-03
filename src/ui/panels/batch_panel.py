from pathlib import Path

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QWidget,
)

from core.batch import BatchJob, BatchOperation, run_batch
from ui.dialogs.progress_dialog import ProgressDialog
from ui.panels.base_panel import BasePanelWidget
from ui.widgets.drop_zone import DropZone


class BatchPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Batch", parent)
        self._files: list[Path] = []
        self._file_passwords: dict[Path, str | None] = {}  # per-file passwords
        self._supports_preview = False  # operazione multipla
        self._progress_dlg: ProgressDialog | None = None
        self._thread: QThread | None = None
        self._batch_worker = None  # mantiene il riferimento vivo durante il thread
        self._setup_content()

    def _setup_content(self) -> None:
        hint = QLabel(
            "Applica la stessa operazione a più PDF contemporaneamente.",
            self,
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        self._content_layout.addWidget(hint)

        self._drop = DropZone(label_text="Trascina PDF qui o clicca", multiple=True)
        self._drop.files_dropped.connect(self._add_files)
        self._content_layout.addWidget(self._drop)

        self._list = QListWidget(self)
        self._list.setMaximumHeight(110)
        self._content_layout.addWidget(self._list)

        btns = QHBoxLayout()
        rem = QPushButton("Rimuovi", self)
        rem.setObjectName("secondaryButton")
        rem.clicked.connect(self._remove_selected)
        clr = QPushButton("Cancella", self)
        clr.setObjectName("secondaryButton")
        clr.clicked.connect(self._clear)
        btns.addWidget(rem)
        btns.addWidget(clr)
        self._content_layout.addLayout(btns)

        form = QFormLayout()
        self._op_combo = QComboBox(self)
        self._op_combo.setObjectName("formCombo")
        ops = [
            ("Comprimi", BatchOperation.COMPRESS),
            ("Aggiungi watermark", BatchOperation.WATERMARK),
            ("Ruota 90°", BatchOperation.ROTATE),
            ("Aggiungi pagina licenza", BatchOperation.ADD_LICENSE_PAGE),
            ("Aggiungi intestazioni/piè", BatchOperation.ADD_HEADERS_FOOTERS),
            ("Unisci tutti in uno", BatchOperation.MERGE_TO_ONE),
        ]
        for label, op in ops:
            self._op_combo.addItem(label, op)
        form.addRow("Operazione:", self._op_combo)

        self._suffix_label = QLabel(
            "I file risultanti saranno salvati con suffisso nella cartella scelta.",
            self,
        )
        self._suffix_label.setObjectName("hintLabel")
        self._suffix_label.setWordWrap(True)
        self._content_layout.addLayout(form)
        self._content_layout.addWidget(self._suffix_label)

    def _reset_state(self) -> None:
        self._files = []
        self._file_passwords = {}

    def set_current_file(self, path, password="") -> None:
        super().set_current_file(path, password)
        self._apply_btn.setEnabled(True)

    def _add_files(self, paths: list[Path]) -> None:
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                # Controlla se il file è protetto
                pwd = self._check_protected_file(p)
                self._file_passwords[p] = pwd
                # Mostra indicatore visual se file è protetto
                display_name = f"{p.name}" + (" 🔒" if pwd is not None else "")
                self._list.addItem(QListWidgetItem(display_name))

    def _check_protected_file(self, path: Path) -> str | None:
        """
        Controlla se il file è protetto e chiede password se necessario.

        Returns:
            Password se il file è protetto, None altrimenti.
        """
        import pikepdf

        try:
            # Tenta di aprire senza password
            with pikepdf.open(path) as _:
                pass
            return None  # File non protetto
        except pikepdf.PasswordError:
            # File protetto: chiedi password all'utente
            from ui.dialogs.password_dialog import ask_password

            pwd = ask_password(filename=path.name, parent=self)
            if pwd is None:
                # Utente ha annullato: aggiungiamo comunque il file con None
                # L'errore sarà esplicito durante il batch
                QMessageBox.warning(
                    self,
                    "File protetto",
                    f"{path.name} è protetto ma nessuna password fornita. "
                    "L'operazione batch fallirà per questo file.",
                )
                return None
            return pwd
        except Exception:
            # Errore nel controllo (file non valido, etc.)
            return None

    def _remove_selected(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            removed_file = self._files[row]
            self._list.takeItem(row)
            self._files.pop(row)
            self._file_passwords.pop(removed_file, None)

    def _clear(self) -> None:
        self._list.clear()
        self._files.clear()
        self._file_passwords.clear()

    def _collect_config_impl(self):
        if not self._files:
            QMessageBox.information(self, "Nessun file", "Aggiungi almeno un PDF.")
            return None
        return {"operation": self._op_combo.currentData()}

    def _on_apply(self) -> None:
        config = self._collect_config()
        if not config:
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Seleziona cartella di output", "")
        if not output_dir:
            return

        operation = config["operation"]
        job = BatchJob(
            operation=operation,
            output_dir=Path(output_dir),
            output_suffix=f"_{operation.value}",
            password_map=dict(self._file_passwords),  # Passa le password per-file
        )

        self._progress_dlg = ProgressDialog("Batch in corso…", self)
        self._progress_dlg.cancelled.connect(self._on_cancel)

        self._thread = QThread(self)

        files = list(self._files)
        dlg = self._progress_dlg

        from PyQt6.QtCore import QObject
        from PyQt6.QtCore import pyqtSignal as _ps

        class _Worker(QObject):
            progress = _ps(int, int, str)
            finished = _ps(list)

            def run(self_w):
                def cb(done, total, name):
                    self_w.progress.emit(done, total, name)

                results = run_batch(files, job, progress_callback=cb)
                self_w.finished.emit(results)

        self._batch_worker = _Worker()
        self._batch_worker.moveToThread(self._thread)
        self._batch_worker.progress.connect(dlg.update_progress)
        self._batch_worker.finished.connect(self._on_batch_done)
        self._thread.started.connect(self._batch_worker.run)
        self._thread.start()

        self._apply_btn.setEnabled(False)
        self._progress_dlg.exec()

    def _on_batch_done(self, results) -> None:
        if self._progress_dlg:
            self._progress_dlg.finish()
        if self._thread:
            self._thread.quit()
        self._apply_btn.setEnabled(True)

        failed = [r for r in results if not r.success]
        ok = len(results) - len(failed)
        msg = f"Completato: {ok} file elaborati con successo."
        if failed:
            msg += f"\n{len(failed)} file con errori:\n"
            msg += "\n".join(f"• {r.input_path.name}: {r.error}" for r in failed[:5])
        QMessageBox.information(self, "Batch completato", msg)
        self.status_message.emit(f"Batch completato: {ok}/{len(results)}")

    def _on_cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.quit()
        self._apply_btn.setEnabled(True)

    def _run_core(self, *_) -> Path:
        return Path()  # non usato
