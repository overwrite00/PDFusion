from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.compress import CompressConfig, CompressPreset
from ui.panels.base_panel import BasePanelWidget


class CompressPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Comprimi PDF", parent)
        self._setup_content()

    def _setup_content(self) -> None:
        preset_group = QGroupBox("Preset qualità", self)
        preset_layout = QVBoxLayout(preset_group)

        self._radio_screen = QRadioButton("Schermo — 72 dpi (dimensione minima)", preset_group)
        self._radio_ebook = QRadioButton("eBook — 150 dpi  ✓ consigliato", preset_group)
        self._radio_ebook.setChecked(True)
        self._radio_printer = QRadioButton("Stampante — 300 dpi", preset_group)
        self._radio_prepress = QRadioButton("Prestampa — 300 dpi (qualità massima)", preset_group)
        self._radio_custom = QRadioButton("Personalizzato", preset_group)

        for r in [
            self._radio_screen,
            self._radio_ebook,
            self._radio_printer,
            self._radio_prepress,
            self._radio_custom,
        ]:
            preset_layout.addWidget(r)

        self._content_layout.addWidget(preset_group)

        # Opzioni custom
        self._custom_group = QGroupBox("Opzioni personalizzate", self)
        self._custom_group.setEnabled(False)
        form = QFormLayout(self._custom_group)

        self._dpi_spin = QSpinBox(self._custom_group)
        self._dpi_spin.setObjectName("formSpin")
        self._dpi_spin.setRange(36, 600)
        self._dpi_spin.setValue(150)
        self._dpi_spin.setSuffix(" dpi")
        form.addRow("DPI immagini:", self._dpi_spin)

        self._quality_slider = QSlider(Qt.Orientation.Horizontal, self._custom_group)
        self._quality_slider.setRange(10, 100)
        self._quality_slider.setValue(75)
        self._quality_label = QLabel("75%", self._custom_group)
        self._quality_slider.valueChanged.connect(lambda v: self._quality_label.setText(f"{v}%"))

        q_row_widget = QWidget(self._custom_group)
        from PyQt6.QtWidgets import QHBoxLayout

        q_row = QHBoxLayout(q_row_widget)
        q_row.setContentsMargins(0, 0, 0, 0)
        q_row.addWidget(self._quality_slider)
        q_row.addWidget(self._quality_label)
        form.addRow("Qualità JPEG:", q_row_widget)

        self._remove_meta_check = QCheckBox("Rimuovi metadati", self._custom_group)
        form.addRow(self._remove_meta_check)

        self._flatten_check = QCheckBox("Appiattisci annotazioni", self._custom_group)
        form.addRow(self._flatten_check)

        self._content_layout.addWidget(self._custom_group)

        self._radio_custom.toggled.connect(self._custom_group.setEnabled)

    def _collect_config_impl(self) -> CompressConfig:
        if self._radio_screen.isChecked():
            return CompressConfig(preset=CompressPreset.SCREEN)
        if self._radio_ebook.isChecked():
            return CompressConfig(preset=CompressPreset.EBOOK)
        if self._radio_printer.isChecked():
            return CompressConfig(preset=CompressPreset.PRINTER)
        if self._radio_prepress.isChecked():
            return CompressConfig(preset=CompressPreset.PREPRESS)
        return CompressConfig(
            preset=CompressPreset.CUSTOM,
            custom_dpi=self._dpi_spin.value(),
            custom_jpeg_quality=self._quality_slider.value(),
            remove_metadata=self._remove_meta_check.isChecked(),
            flatten_annotations=self._flatten_check.isChecked(),
        )

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.compress import compress

        compress(input_path, output_path, config, password or None)
        return output_path
