from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from core.pdf_to_images import ExportImagesConfig, ImageFormat
from ui.panels.base_panel import BasePanelWidget
from ui.widgets.page_range_input import PageRangeInput


class ExportImagesPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("PDF → Immagini", parent)
        self._supports_preview = False   # output immagini, non PDF
        self._setup_content()

    def _setup_content(self) -> None:
        form = QFormLayout()

        self._format_combo = QComboBox(self)
        self._format_combo.setObjectName("formCombo")
        self._format_combo.addItem("PNG", ImageFormat.PNG)
        self._format_combo.addItem("JPEG", ImageFormat.JPEG)
        self._format_combo.addItem("TIFF", ImageFormat.TIFF)
        form.addRow("Formato:", self._format_combo)

        self._dpi_spin = QSpinBox(self)
        self._dpi_spin.setObjectName("formSpin")
        self._dpi_spin.setRange(36, 600)
        self._dpi_spin.setValue(150)
        self._dpi_spin.setSuffix(" dpi")
        form.addRow("Risoluzione:", self._dpi_spin)

        form.addRow(QLabel("Range pagine (vuoto = tutte):", self))
        self._range_input = PageRangeInput()
        form.addRow(self._range_input)

        self._content_layout.addLayout(form)


    def _collect_config(self) -> dict:
        return {
            "format": self._format_combo.currentData(),
            "dpi": self._dpi_spin.value(),
            "range": self._range_input.text().strip() or None,
        }

    def _on_apply(self) -> None:
        if not self._current_path:
            return
        config = self._collect_config()

        output_dir = QFileDialog.getExistingDirectory(
            self, "Seleziona cartella di output", str(self._current_path.parent)
        )
        if not output_dir:
            return

        self._apply_btn.setEnabled(False)
        self.status_message.emit("Esportazione immagini in corso…")

        from PyQt6.QtCore import QThread

        from ui.panels.base_panel import _Worker

        def _do(input_path, out, pwd, cfg):
            from core.pdf_to_images import export_pages_as_images
            result = export_pages_as_images(
                input_path,
                Path(output_dir),
                ExportImagesConfig(
                    format=cfg["format"],
                    dpi=cfg["dpi"],
                    page_range=cfg["range"],
                ),
                pwd or None,
            )
            return result[0] if result else input_path

        self._thread = QThread(self)
        self._worker = _Worker(_do, self._current_path, self._current_path, self._current_password, config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _run_core(self, *_) -> Path:
        return Path()  # non usato
