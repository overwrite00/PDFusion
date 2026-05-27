from pathlib import Path

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ui.panels.base_panel import BasePanelWidget
from ui.widgets.page_range_input import PageRangeInput


class RotatePanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Ruota pagine", parent)
        self._setup_content()

    def _setup_content(self) -> None:
        # Angolo
        angle_group = QGroupBox("Angolo di rotazione", self)
        angle_layout = QHBoxLayout(angle_group)
        self._radio_90 = QRadioButton("90°", angle_group)
        self._radio_90.setChecked(True)
        self._radio_180 = QRadioButton("180°", angle_group)
        self._radio_270 = QRadioButton("270°", angle_group)
        for r in [self._radio_90, self._radio_180, self._radio_270]:
            angle_layout.addWidget(r)
        self._content_layout.addWidget(angle_group)

        # Pagine
        pages_group = QGroupBox("Pagine", self)
        pages_layout = QVBoxLayout(pages_group)
        self._radio_all = QRadioButton("Tutte", pages_group)
        self._radio_all.setChecked(True)
        self._radio_range = QRadioButton("Range personalizzato:", pages_group)
        pages_layout.addWidget(self._radio_all)
        pages_layout.addWidget(self._radio_range)

        self._range_input = PageRangeInput()
        self._range_input.setEnabled(False)
        pages_layout.addWidget(self._range_input)

        self._radio_range.toggled.connect(self._range_input.setEnabled)
        self._content_layout.addWidget(pages_group)

    def _collect_config_impl(self) -> dict:
        angle = 90 if self._radio_90.isChecked() else (180 if self._radio_180.isChecked() else 270)
        if self._radio_all.isChecked():
            return {"angle": angle, "indices": []}
        else:
            if not self._range_input.is_valid():
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Range non valido",
                    "Il range di pagine inserito non è valido.\nEsempio corretto: 1-3, 5, 7-9",
                )
                return None  # type: ignore[return-value]
            from utils.page_range_parser import ranges_to_indices

            ranges = self._range_input.get_ranges()
            return {"angle": angle, "indices": ranges_to_indices(ranges) if ranges else []}

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.rotate import rotate_pages

        rotate_pages(
            input_path,
            config["indices"],
            config["angle"],
            output_path,
            password or None,
        )
        return output_path
