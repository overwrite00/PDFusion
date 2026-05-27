from pathlib import Path

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QWidget,
)

from core.images_to_pdf import FitMode
from ui.panels.base_panel import BasePanelWidget
from ui.widgets.drop_zone import DropZone


class ImportImagesPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Immagini → PDF", parent)
        self._images: list[Path] = []
        self._supports_preview = False  # input immagini, non PDF: preview non applicabile
        self._setup_content()

    def _setup_content(self) -> None:
        self._drop = DropZone(
            accept_extensions=(".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"),
            label_text="Trascina immagini qui\no clicca per selezionarle",
            multiple=True,
        )
        self._drop.files_dropped.connect(self._add_images)
        self._content_layout.addWidget(self._drop)

        self._list = QListWidget(self)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setMaximumHeight(140)
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
        self._fit_combo = QComboBox(self)
        self._fit_combo.setObjectName("formCombo")
        self._fit_combo.addItem("Adatta alla pagina (A4)", FitMode.FIT_PAGE)
        self._fit_combo.addItem("Dimensioni originali", FitMode.ORIGINAL_SIZE)
        self._fit_combo.addItem("Pagina fissa A4", FitMode.FIXED_PAGE)
        form.addRow("Modalità:", self._fit_combo)

        self._dpi_spin = QSpinBox(self)
        self._dpi_spin.setObjectName("formSpin")
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setValue(150)
        self._dpi_spin.setSuffix(" dpi")
        form.addRow("DPI presunto:", self._dpi_spin)
        self._content_layout.addLayout(form)

    def _add_images(self, paths: list[Path]) -> None:
        for p in paths:
            if p not in self._images:
                self._images.append(p)
                self._list.addItem(QListWidgetItem(p.name))

    def _remove_selected(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self._images.pop(row)

    def _clear(self) -> None:
        self._list.clear()
        self._images.clear()

    def _reset_state(self) -> None:
        self._images = []

    def set_current_file(self, path, password="") -> None:
        super().set_current_file(path, password)
        self._apply_btn.setEnabled(True)

    def _collect_config_impl(self):
        if not self._images:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(self, "Nessuna immagine", "Aggiungi almeno un'immagine.")
            return None
        return {
            "images": list(self._images),
            "fit_mode": self._fit_combo.currentData(),
            "dpi": self._dpi_spin.value(),
        }

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.images_to_pdf import ImagesToPDFConfig, images_to_pdf

        images_to_pdf(
            config["images"],
            output_path,
            ImagesToPDFConfig(fit_mode=config["fit_mode"], dpi=config["dpi"]),
        )
        return output_path
