from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.insert_page import PAGE_SIZES
from ui.panels.base_panel import BasePanelWidget


class InsertPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Inserisci pagina", parent)
        self._source_path: Path | None = None
        self._total_pages: int = 1
        self._setup_content()

    def _setup_content(self) -> None:
        # Posizione
        pos_group = QGroupBox("Posizione di inserimento", self)
        pos_form = QFormLayout(pos_group)
        self._pos_spin = QSpinBox(pos_group)
        self._pos_spin.setObjectName("formSpin")
        self._pos_spin.setRange(1, 9999)
        self._pos_spin.setValue(1)
        pos_form.addRow("Inserisci alla posizione:", self._pos_spin)
        hint = QLabel("1 = prima di tutto, N+1 = in fondo.", pos_group)
        hint.setObjectName("hintLabel")
        pos_form.addRow(hint)
        self._content_layout.addWidget(pos_group)

        # Tipo pagina
        type_group = QGroupBox("Tipo di pagina", self)
        type_layout = QVBoxLayout(type_group)
        self._radio_blank = QRadioButton("Pagina bianca", type_group)
        self._radio_blank.setChecked(True)
        self._radio_from_pdf = QRadioButton("Da un altro PDF", type_group)
        type_layout.addWidget(self._radio_blank)

        # Dimensione pagina bianca
        size_row = QHBoxLayout()
        size_row.setContentsMargins(20, 0, 0, 0)
        self._size_combo = QComboBox(type_group)
        self._size_combo.setObjectName("formCombo")
        for size_name in PAGE_SIZES:
            self._size_combo.addItem(size_name)
        size_row.addWidget(self._size_combo)
        size_row.addStretch()
        type_layout.addLayout(size_row)

        type_layout.addWidget(self._radio_from_pdf)

        src_row = QHBoxLayout()
        src_row.setContentsMargins(20, 0, 0, 0)
        self._src_btn = QPushButton("Scegli PDF sorgente…", type_group)
        self._src_btn.setObjectName("secondaryButton")
        self._src_btn.setEnabled(False)
        self._src_btn.clicked.connect(self._browse_source)
        src_row.addWidget(self._src_btn)
        type_layout.addLayout(src_row)

        self._src_label = QLabel("Nessun file selezionato", type_group)
        self._src_label.setObjectName("hintLabel")
        type_layout.addWidget(self._src_label)

        self._radio_from_pdf.toggled.connect(self._src_btn.setEnabled)
        self._radio_blank.toggled.connect(self._size_combo.setEnabled)
        self._content_layout.addWidget(type_group)

    def _reset_state(self) -> None:
        self._source_path = None
        self._total_pages = 1

    def _on_file_changed(self, path) -> None:
        if path:
            import fitz

            try:
                doc = fitz.open(str(path))
                self._total_pages = doc.page_count
                doc.close()
                self._pos_spin.setMaximum(self._total_pages + 1)
            except Exception:
                pass

    def _browse_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona PDF sorgente", "", "PDF (*.pdf)")
        if path:
            self._source_path = Path(path)
            self._src_label.setText(Path(path).name)

    def _collect_config_impl(self):
        mode = "blank" if self._radio_blank.isChecked() else "from_pdf"
        if mode == "from_pdf" and not self._source_path:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(self, "File mancante", "Seleziona il PDF sorgente.")
            return None
        return {
            "mode": mode,
            "position": self._pos_spin.value(),
            "page_size": self._size_combo.currentText(),
            "source_path": self._source_path,
        }

    def _run_core(self, input_path, output_path, password, config) -> Path:
        pwd = password or None
        if config["mode"] == "blank":
            from core.insert_page import insert_blank_page

            insert_blank_page(input_path, config["position"], output_path, config["page_size"], pwd)
        else:
            from core.insert_page import insert_from_pdf

            insert_from_pdf(
                input_path, config["source_path"], [], config["position"], output_path, pwd
            )
        return output_path
