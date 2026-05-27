from pathlib import Path

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.panels.base_panel import BasePanelWidget
from ui.widgets.drop_zone import DropZone


class MergePanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Unisci PDF", parent)
        self._insert_path: Path | None = None
        self._total_pages: int = 1
        self._setup_content()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_content(self) -> None:
        # --- File base (quello aperto) ---
        base_group = QGroupBox("File base", self)
        base_layout = QVBoxLayout(base_group)
        self._base_label = QLabel("Nessun file aperto", base_group)
        self._base_label.setObjectName("hintLabel")
        self._base_label.setWordWrap(True)
        base_layout.addWidget(self._base_label)
        self._content_layout.addWidget(base_group)

        # --- File da inserire ---
        insert_group = QGroupBox("File da inserire", self)
        insert_layout = QVBoxLayout(insert_group)

        self._drop = DropZone(
            label_text="Trascina PDF qui\no clicca per selezionarlo",
            multiple=False,
        )
        self._drop.files_dropped.connect(self._on_file_dropped)
        insert_layout.addWidget(self._drop)

        path_row = QHBoxLayout()
        self._insert_label = QLabel("Nessun file selezionato", insert_group)
        self._insert_label.setObjectName("hintLabel")
        self._insert_label.setWordWrap(False)
        path_row.addWidget(self._insert_label, stretch=1)

        clear_btn = QPushButton("×", insert_group)
        clear_btn.setObjectName("secondaryButton")
        clear_btn.setFixedWidth(32)
        clear_btn.setToolTip("Rimuovi il file selezionato")
        clear_btn.clicked.connect(self._clear_insert)
        path_row.addWidget(clear_btn)
        insert_layout.addLayout(path_row)
        self._content_layout.addWidget(insert_group)

        # --- Posizione di inserimento ---
        pos_group = QGroupBox("Posizione nel file base", self)
        pos_layout = QVBoxLayout(pos_group)

        page_row = QHBoxLayout()
        page_row.setContentsMargins(0, 0, 0, 0)
        self._radio_page = QRadioButton("Dopo la pagina:", pos_group)
        self._page_spin = QSpinBox(pos_group)
        self._page_spin.setObjectName("formSpin")
        self._page_spin.setRange(1, 1)
        self._page_spin.setValue(1)
        self._page_spin.setEnabled(False)
        page_row.addWidget(self._radio_page)
        page_row.addWidget(self._page_spin)
        page_row.addStretch()
        pos_layout.addLayout(page_row)

        self._radio_end = QRadioButton("In coda (dopo l'ultima pagina)", pos_group)
        self._radio_end.setChecked(True)
        pos_layout.addWidget(self._radio_end)

        hint_pos = QLabel(
            "Il file inserito apparirà nel punto scelto; "
            "le pagine del file base si sposteranno di conseguenza.",
            pos_group,
        )
        hint_pos.setObjectName("hintLabel")
        hint_pos.setWordWrap(True)
        pos_layout.addWidget(hint_pos)

        # Abilita/disabilita lo spinbox in base alla scelta
        self._radio_page.toggled.connect(self._page_spin.setEnabled)

        self._content_layout.addWidget(pos_group)

    # ------------------------------------------------------------------
    # Stato interno
    # ------------------------------------------------------------------

    def _reset_state(self) -> None:
        self._insert_path = None
        self._total_pages = 1

    # ------------------------------------------------------------------
    # Gestione file da inserire
    # ------------------------------------------------------------------

    def _on_file_dropped(self, paths: list[Path]) -> None:
        if paths:
            p = paths[0]
            self._insert_path = p
            name = p.name
            self._insert_label.setText(name if len(name) <= 35 else f"…{name[-32:]}")
            self._update_buttons()

    def _clear_insert(self) -> None:
        self._insert_path = None
        self._insert_label.setText("Nessun file selezionato")
        self._update_buttons()

    # ------------------------------------------------------------------
    # Aggiornamenti in risposta al cambio di file base
    # ------------------------------------------------------------------

    def _on_file_changed(self, path: Path | None) -> None:
        if path:
            try:
                import fitz

                doc = fitz.open(str(path))
                self._total_pages = doc.page_count
                doc.close()
            except Exception:
                self._total_pages = 1

            label_txt = (
                f"{path.name}  "
                f"({self._total_pages} "
                f"{'pagina' if self._total_pages == 1 else 'pagine'})"
            )
            self._base_label.setText(label_txt)

            # Lo spinbox copre solo gli spazi intermedi (non l'ultimo = "in coda")
            max_spin = max(1, self._total_pages - 1)
            self._page_spin.setRange(1, max_spin)
            self._page_spin.setValue(min(self._page_spin.value(), max_spin))
        else:
            self._total_pages = 1
            self._base_label.setText("Nessun file aperto")
            self._page_spin.setRange(1, 1)

    def set_current_file(self, path: Path | None, password: str = "") -> None:
        super().set_current_file(path, password)
        # Applica richiede entrambi i file: base E da inserire
        self._update_buttons()

    def _update_buttons(self) -> None:
        both = self._current_path is not None and self._insert_path is not None
        self._apply_btn.setEnabled(both)
        self._preview_btn.setEnabled(both)

    # ------------------------------------------------------------------
    # Logica core
    # ------------------------------------------------------------------

    def _collect_config(self):
        if not self._insert_path:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "File mancante",
                "Seleziona il PDF da inserire nel file base.",
            )
            return None

        if self._radio_end.isChecked():
            after_page = self._total_pages  # append in coda
        else:
            after_page = self._page_spin.value()

        return {
            "insert_path": self._insert_path,
            "after_page": after_page,
        }

    def _run_core(self, input_path: Path, output_path: Path, password: str, config) -> Path:
        from core.merge import insert_pdf_at

        insert_pdf_at(
            input_path,
            config["insert_path"],
            config["after_page"],
            output_path,
            base_password=password or None,
        )
        return output_path
