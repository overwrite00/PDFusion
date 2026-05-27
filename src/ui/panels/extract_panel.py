from pathlib import Path

from PyQt6.QtWidgets import QLabel, QWidget

from ui.panels.base_panel import BasePanelWidget
from ui.widgets.page_range_input import PageRangeInput


class ExtractPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Estrai pagine", parent)
        self._setup_content()

    def _setup_content(self) -> None:
        hint = QLabel("Inserisci le pagine da estrarre nel nuovo PDF:", self)
        hint.setObjectName("hintLabel")
        self._content_layout.addWidget(hint)

        self._range_input = PageRangeInput(placeholder="es. 1-3, 5, 7-9")
        self._content_layout.addWidget(self._range_input)

    def _on_file_changed(self, path) -> None:
        if path:
            import fitz

            try:
                doc = fitz.open(str(path))
                self._range_input.set_total_pages(doc.page_count)
                doc.close()
            except Exception:
                pass

    def _collect_config_impl(self):
        if not self._range_input.is_valid():
            return None
        ranges = self._range_input.get_ranges()
        if not ranges:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(self, "Range vuoto", "Inserisci almeno una pagina da estrarre.")
            return None
        return {"ranges": ranges}

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.extract_pages import extract_pages

        extract_pages(input_path, config["ranges"], output_path, password or None)
        return output_path
