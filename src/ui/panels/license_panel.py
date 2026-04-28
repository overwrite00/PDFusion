from __future__ import annotations

import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QWidget,
)

from core.license_page import LICENSE_LABELS, LicenseConfig
from ui.panels.base_panel import BasePanelWidget


class LicensePanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Pagina licenza", parent)
        self._cover_image_path: Path | None = None
        self._setup_content()

    def _setup_content(self) -> None:
        hint = QLabel(
            "La pagina di licenza sarà inserita in prima posizione nel PDF.",
            self,
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        self._content_layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(10)

        # Tipo di licenza
        self._license_combo = QComboBox(self)
        self._license_combo.setObjectName("formCombo")
        for license_type, label in LICENSE_LABELS.items():
            self._license_combo.addItem(label, license_type)
        form.addRow("Tipo di licenza:", self._license_combo)

        # Autore
        self._author_edit = QLineEdit(self)
        self._author_edit.setPlaceholderText("Nome autore o organizzazione")
        form.addRow("Autore:", self._author_edit)

        # Anno
        self._year_spin = QSpinBox(self)
        self._year_spin.setObjectName("formSpin")
        self._year_spin.setRange(1900, 2100)
        self._year_spin.setValue(datetime.date.today().year)
        form.addRow("Anno:", self._year_spin)

        # Titolo
        self._title_edit = QLineEdit(self)
        self._title_edit.setPlaceholderText("Titolo documento (opzionale)")
        form.addRow("Titolo:", self._title_edit)

        # Lingua
        lang_widget = QWidget(self)
        lang_layout = QHBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.setSpacing(16)
        self._rb_it = QRadioButton("Italiano", lang_widget)
        self._rb_it.setChecked(True)
        self._rb_en = QRadioButton("English", lang_widget)
        lang_layout.addWidget(self._rb_it)
        lang_layout.addWidget(self._rb_en)
        lang_layout.addStretch()
        form.addRow("Lingua:", lang_widget)

        # Immagine di copertina
        cover_widget = QWidget(self)
        cover_layout = QHBoxLayout(cover_widget)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.setSpacing(6)

        self._cover_label = QLabel("Nessuna immagine", cover_widget)
        self._cover_label.setObjectName("hintLabel")
        self._cover_label.setWordWrap(False)
        cover_layout.addWidget(self._cover_label, stretch=1)

        pick_btn = QPushButton("Scegli…", cover_widget)
        pick_btn.setObjectName("secondaryButton")
        pick_btn.setFixedWidth(80)
        pick_btn.clicked.connect(self._pick_cover_image)
        cover_layout.addWidget(pick_btn)

        clear_btn = QPushButton("×", cover_widget)
        clear_btn.setObjectName("secondaryButton")
        clear_btn.setFixedWidth(32)
        clear_btn.setToolTip("Rimuovi immagine di copertina")
        clear_btn.clicked.connect(self._clear_cover_image)
        cover_layout.addWidget(clear_btn)

        form.addRow("Copertina:", cover_widget)

        self._content_layout.addLayout(form)

    # ------------------------------------------------------------------
    # Cover image helpers
    # ------------------------------------------------------------------

    def _pick_cover_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona immagine di copertina",
            "",
            "Immagini (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.gif)",
        )
        if path:
            self._cover_image_path = Path(path)
            name = self._cover_image_path.name
            # Tronca il nome se troppo lungo
            self._cover_label.setText(name if len(name) <= 30 else f"…{name[-27:]}")

    def _clear_cover_image(self) -> None:
        self._cover_image_path = None
        self._cover_label.setText("Nessuna immagine")

    # ------------------------------------------------------------------
    # BasePanelWidget overrides
    # ------------------------------------------------------------------

    def _reset_state(self) -> None:
        self._cover_image_path = None

    def _collect_config(self) -> LicenseConfig:
        author = self._author_edit.text().strip()
        if not author:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Campo obbligatorio", "Inserisci il nome dell'autore.")
            return None  # type: ignore[return-value]
        return LicenseConfig(
            license_type=self._license_combo.currentData(),
            author=author,
            year=self._year_spin.value(),
            document_title=self._title_edit.text().strip() or None,
            language="it" if self._rb_it.isChecked() else "en",
            cover_image_path=self._cover_image_path,
        )

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.license_page import insert_license_page
        insert_license_page(input_path, output_path, config, password or None)
        return output_path
