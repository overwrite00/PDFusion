from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.panels.base_panel import BasePanelWidget
from ui.widgets.page_range_input import PageRangeInput


class SplitPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Dividi PDF", parent)
        self._supports_preview = False  # produce file multipli
        self._setup_content()

    def _setup_content(self) -> None:
        # Modalità: ogni N pagine oppure range custom
        mode_group = QGroupBox("Modalità di divisione", self)
        mode_layout = QVBoxLayout(mode_group)

        self._radio_n = QRadioButton("Ogni N pagine", mode_group)
        self._radio_n.setChecked(True)
        mode_layout.addWidget(self._radio_n)

        n_row = QHBoxLayout()
        n_row.setContentsMargins(20, 0, 0, 0)
        self._n_spin = QSpinBox(mode_group)
        self._n_spin.setObjectName("formSpin")
        self._n_spin.setRange(1, 9999)
        self._n_spin.setValue(1)
        self._n_spin.setSuffix(" pag.")
        n_row.addWidget(self._n_spin)
        n_row.addStretch()
        mode_layout.addLayout(n_row)

        self._radio_range = QRadioButton("Range personalizzato", mode_group)
        mode_layout.addWidget(self._radio_range)

        range_row = QHBoxLayout()
        range_row.setContentsMargins(20, 0, 0, 0)
        self._range_input = PageRangeInput(placeholder="es. 1-3, 5, 7-9")
        range_row.addWidget(self._range_input)
        mode_layout.addLayout(range_row)

        self._content_layout.addWidget(mode_group)

        hint = QLabel(
            "I file risultanti saranno salvati nella cartella di destinazione "
            "con suffisso numerico (_001, _002…).",
            self,
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        self._content_layout.addWidget(hint)

        # Abilita/disabilita campi in base alla selezione
        self._radio_n.toggled.connect(lambda on: self._n_spin.setEnabled(on))
        self._radio_range.toggled.connect(lambda on: self._range_input.setEnabled(on))
        self._range_input.setEnabled(False)

    def _collect_config_impl(self):
        if self._radio_n.isChecked():
            return {"mode": "n", "n": self._n_spin.value()}
        else:
            if not self._range_input.is_valid():
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Range non valido",
                    "Il range di pagine inserito non è valido.\nEsempio corretto: 1-3, 5, 7-9",
                )
                return None
            ranges = self._range_input.get_ranges()
            if not ranges:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(self, "Range vuoto", "Nessuna pagina specificata nel range.")
                return None
            return {"mode": "ranges", "ranges": ranges}

    def _on_apply(self) -> None:
        if not self._current_path:
            return
        config = self._collect_config()
        if config is None:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self, "Seleziona cartella di output", str(self._current_path.parent)
        )
        if not output_dir:
            return

        self._apply_btn.setEnabled(False)
        self.status_message.emit("Divisione in corso…")

        from PyQt6.QtCore import QThread

        from ui.panels.base_panel import _Worker

        def _do_split(input_path, out_path, pwd, cfg):
            if cfg["mode"] == "n":
                from core.split import split_every_n

                results = split_every_n(input_path, cfg["n"], Path(output_dir), pwd or None)
            else:
                from core.split import split_ranges

                results = split_ranges(input_path, cfg["ranges"], Path(output_dir), pwd or None)
            return results[0] if results else input_path

        self._thread = QThread(self)
        self._worker = _Worker(
            _do_split,
            self._current_path,
            self._current_path,
            self._current_password,
            config,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _run_core(self, input_path, output_path, password, config) -> Path:
        return output_path  # non usato — _on_apply override
