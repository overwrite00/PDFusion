from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.watermark import (
    PageSelection,
    WatermarkConfig,
    WatermarkMode,
    WatermarkPosition,
)
from ui.panels.base_panel import BasePanelWidget
from utils.config import WATERMARK_PRESETS_IT


class WatermarkPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Watermark / Filigrana", parent)
        self._image_path: Path | None = None
        self._setup_content()

    def _setup_content(self) -> None:
        tabs = QTabWidget(self)

        # --- Tab Testo ---
        text_tab = QWidget(tabs)
        text_layout = QVBoxLayout(text_tab)
        text_layout.setContentsMargins(8, 8, 8, 8)

        text_layout.addWidget(QLabel("Preset:", text_tab))
        self._preset_list = QListWidget(text_tab)
        for preset in WATERMARK_PRESETS_IT:
            self._preset_list.addItem(preset)
        self._preset_list.setMaximumHeight(130)
        self._preset_list.currentTextChanged.connect(self._on_preset_selected)
        text_layout.addWidget(self._preset_list)

        text_layout.addWidget(QLabel("Testo personalizzato:", text_tab))
        self._text_edit = QLineEdit(text_tab)
        self._text_edit.setPlaceholderText("Inserisci testo watermark…")
        text_layout.addWidget(self._text_edit)

        font_row = QFormLayout()
        self._font_size_spin = QSpinBox(text_tab)
        self._font_size_spin.setObjectName("formSpin")
        self._font_size_spin.setRange(8, 200)
        self._font_size_spin.setValue(48)
        font_row.addRow("Dimensione font:", self._font_size_spin)
        text_layout.addLayout(font_row)
        tabs.addTab(text_tab, "Testo")

        # --- Tab Immagine ---
        img_tab = QWidget(tabs)
        img_layout = QVBoxLayout(img_tab)
        img_layout.setContentsMargins(8, 8, 8, 8)

        self._img_btn = QPushButton("Carica immagine PNG/SVG…", img_tab)
        self._img_btn.setObjectName("secondaryButton")
        self._img_btn.clicked.connect(self._browse_image)
        img_layout.addWidget(self._img_btn)

        self._img_label = QLabel("Nessuna immagine selezionata", img_tab)
        self._img_label.setObjectName("hintLabel")
        self._img_label.setWordWrap(True)
        img_layout.addWidget(self._img_label)

        scale_form = QFormLayout()
        self._scale_slider = QSlider(Qt.Orientation.Horizontal, img_tab)
        self._scale_slider.setRange(10, 200)
        self._scale_slider.setValue(50)
        self._scale_label = QLabel("50%", img_tab)
        self._scale_slider.valueChanged.connect(lambda v: self._scale_label.setText(f"{v}%"))
        scale_row = QWidget(img_tab)
        sr_layout = QHBoxLayout(scale_row)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.addWidget(self._scale_slider)
        sr_layout.addWidget(self._scale_label)
        scale_form.addRow("Scala:", scale_row)
        img_layout.addLayout(scale_form)
        img_layout.addStretch()
        tabs.addTab(img_tab, "Immagine")

        self._tabs = tabs
        self._content_layout.addWidget(tabs)

        # --- Posizionamento ---
        pos_group = QGroupBox("Posizione", self)
        pos_layout = QVBoxLayout(pos_group)
        self._pos_combo = QComboBox(pos_group)
        self._pos_combo.setObjectName("formCombo")
        positions = [
            ("Diagonale centrale", WatermarkPosition.CENTER_DIAGONAL),
            ("Centro", WatermarkPosition.CENTER),
            ("In alto a sinistra", WatermarkPosition.TOP_LEFT),
            ("In alto a destra", WatermarkPosition.TOP_RIGHT),
            ("In basso a sinistra", WatermarkPosition.BOTTOM_LEFT),
            ("In basso a destra", WatermarkPosition.BOTTOM_RIGHT),
            ("Griglia (Tiled)", WatermarkPosition.TILED),
        ]
        for label, value in positions:
            self._pos_combo.addItem(label, value)
        pos_layout.addWidget(self._pos_combo)

        rot_form = QFormLayout()
        self._rotation_spin = QDoubleSpinBox(pos_group)
        self._rotation_spin.setObjectName("formSpin")
        self._rotation_spin.setRange(-180, 180)
        self._rotation_spin.setValue(-45)
        self._rotation_spin.setSuffix("°")
        rot_form.addRow("Rotazione:", self._rotation_spin)
        pos_layout.addLayout(rot_form)

        self._content_layout.addWidget(pos_group)

        # --- Opacità ---
        opacity_group = QGroupBox("Opacità", self)
        op_layout = QHBoxLayout(opacity_group)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal, opacity_group)
        self._opacity_slider.setRange(10, 90)
        self._opacity_slider.setValue(30)
        self._opacity_label = QLabel("30%", opacity_group)
        self._opacity_slider.valueChanged.connect(lambda v: self._opacity_label.setText(f"{v}%"))
        op_layout.addWidget(self._opacity_slider)
        op_layout.addWidget(self._opacity_label)
        self._content_layout.addWidget(opacity_group)

        # --- Applica a ---
        apply_group = QGroupBox("Applica a", self)
        apply_layout = QVBoxLayout(apply_group)
        self._radio_all = QRadioButton("Tutte le pagine", apply_group)
        self._radio_all.setChecked(True)
        self._radio_first_last = QRadioButton("Prima e ultima", apply_group)
        self._radio_first = QRadioButton("Solo prima", apply_group)
        self._radio_last = QRadioButton("Solo ultima", apply_group)
        for r in [self._radio_all, self._radio_first_last, self._radio_first, self._radio_last]:
            apply_layout.addWidget(r)
        self._content_layout.addWidget(apply_group)

    def _reset_state(self) -> None:
        self._image_path = None

    def _on_preset_selected(self, text: str) -> None:
        if text:
            self._text_edit.setText(text)

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona immagine", "", "Immagini (*.png *.jpg *.jpeg *.svg)"
        )
        if path:
            self._image_path = Path(path)
            self._img_label.setText(Path(path).name)

    def _collect_config_impl(self) -> WatermarkConfig:
        is_text = self._tabs.currentIndex() == 0

        if is_text:
            mode = WatermarkMode.TEXT
            text = self._text_edit.text().strip() or "RISERVATO"
        else:
            mode = WatermarkMode.IMAGE
            text = ""
            if not self._image_path:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.information(self, "Immagine mancante", "Seleziona un'immagine.")
                return None  # type: ignore[return-value]

        if self._radio_first_last.isChecked():
            page_sel = PageSelection.FIRST_AND_LAST
        elif self._radio_first.isChecked():
            page_sel = PageSelection.FIRST_ONLY
        elif self._radio_last.isChecked():
            page_sel = PageSelection.LAST_ONLY
        else:
            page_sel = PageSelection.ALL

        return WatermarkConfig(
            mode=mode,
            text=text,
            font_size=self._font_size_spin.value(),
            image_path=self._image_path,
            image_scale=self._scale_slider.value() / 100.0,
            position=self._pos_combo.currentData(),
            rotation=self._rotation_spin.value(),
            opacity=self._opacity_slider.value() / 100.0,
            page_selection=page_sel,
        )

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.watermark import apply_watermark

        apply_watermark(input_path, output_path, config, password or None)
        return output_path
