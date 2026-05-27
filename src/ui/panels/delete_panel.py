from pathlib import Path

from PyQt6.QtWidgets import (
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


class DeletePanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Elimina pagina", parent)
        self._current_page_idx: int = 0
        self._total_pages: int = 0
        self._setup_content()

    def _setup_content(self) -> None:
        mode_group = QGroupBox("Seleziona pagine da eliminare", self)
        layout = QVBoxLayout(mode_group)

        self._radio_current = QRadioButton("Pagina corrente", mode_group)
        self._radio_current.setChecked(True)
        self._current_label = QLabel("(nessun documento aperto)", mode_group)
        self._current_label.setObjectName("hintLabel")
        layout.addWidget(self._radio_current)
        layout.addWidget(self._current_label)

        self._radio_number = QRadioButton("Per numero", mode_group)
        layout.addWidget(self._radio_number)

        spin_row = QHBoxLayout()
        spin_row.setContentsMargins(20, 0, 0, 0)
        self._page_spin = QSpinBox(mode_group)
        self._page_spin.setObjectName("formSpin")
        self._page_spin.setRange(1, 9999)
        self._page_spin.setEnabled(False)
        spin_row.addWidget(self._page_spin)
        spin_row.addStretch()
        layout.addLayout(spin_row)

        self._radio_range = QRadioButton("Range personalizzato", mode_group)
        layout.addWidget(self._radio_range)

        range_row = QHBoxLayout()
        range_row.setContentsMargins(20, 0, 0, 0)
        self._range_input = PageRangeInput()
        self._range_input.setEnabled(False)
        range_row.addWidget(self._range_input)
        layout.addLayout(range_row)

        self._content_layout.addWidget(mode_group)

        warn = QLabel("⚠ L'operazione non può lasciare il PDF senza pagine.", self)
        warn.setObjectName("hintLabel")
        warn.setWordWrap(True)
        self._content_layout.addWidget(warn)

        # Connessioni
        self._radio_current.toggled.connect(
            lambda on: self._page_spin.setEnabled(False) or self._range_input.setEnabled(False)
        )
        self._radio_number.toggled.connect(self._page_spin.setEnabled)
        self._radio_range.toggled.connect(self._range_input.setEnabled)

    def set_current_page(self, page_idx: int) -> None:
        self._current_page_idx = page_idx
        self._current_label.setText(f"Pagina {page_idx + 1}")

    def _on_file_changed(self, path) -> None:
        if path:
            import fitz

            try:
                doc = fitz.open(str(path))
                self._total_pages = doc.page_count
                doc.close()
                self._page_spin.setMaximum(self._total_pages)
                self._range_input.set_total_pages(self._total_pages)
                # Aggiorna l'etichetta "Pagina corrente" al caricamento iniziale
                self._current_label.setText(f"Pagina {self._current_page_idx + 1}")
            except Exception:
                pass
        else:
            self._current_label.setText("(nessun documento aperto)")
            self._current_page_idx = 0

    def _collect_config_impl(self):
        if self._radio_current.isChecked():
            return {"mode": "current", "index": self._current_page_idx}
        elif self._radio_number.isChecked():
            return {"mode": "number", "number": self._page_spin.value()}
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

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.delete_page import (
            delete_page_by_number,
            delete_pages,
            delete_pages_by_range_string,
        )
        from utils.page_range_parser import format_page_ranges

        mode = config["mode"]
        pwd = password or None

        if mode == "current":
            delete_pages(input_path, [config["index"]], output_path, pwd)
        elif mode == "number":
            delete_page_by_number(input_path, config["number"], output_path, pwd)
        else:
            rng_str = format_page_ranges(config["ranges"])
            delete_pages_by_range_string(input_path, rng_str, output_path, pwd)
        return output_path
