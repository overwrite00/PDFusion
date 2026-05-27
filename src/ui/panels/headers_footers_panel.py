from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.headers_footers import HeaderFooterConfig, HeaderFooterSection
from ui.panels.base_panel import BasePanelWidget


class HeadersFootersPanel(BasePanelWidget):
    """
    Pannello per aggiungere intestazioni e piè di pagina.

    Base-path tracking
    ------------------
    Ogni anteprima viene sempre applicata al documento "pulito" (base-path),
    non al risultato di un'anteprima precedente di questo stesso pannello.
    In questo modo:
    - modificare i testi e rifare Anteprima aggiorna correttamente il risultato
    - svuotare tutti i campi e fare Anteprima ripristina il documento originale
      (meccanismo di rimozione delle intestazioni/piè di pagina)

    Nota: le intestazioni/piè di pagina possono essere RIMOSSE solo nella
    sessione corrente (prima del salvataggio definitivo), svuotando tutti i
    campi oppure usando il pulsante "Rimuovi intestazioni/piè di pagina".
    Una volta salvato il PDF, gli overlay sono permanentemente incorporati.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # Inizializzati prima di super().__init__() perché set_current_file
        # può essere chiamato durante la costruzione della base.
        self._hf_base_path: Path | None = None
        self._hf_base_password: str = ""
        self._hf_last_output: Path | None = None
        super().__init__("Intestazioni / Piè di pagina", parent)
        self._setup_content()

    # ------------------------------------------------------------------
    # Reset state
    # ------------------------------------------------------------------

    def _reset_state(self) -> None:
        self._hf_base_path = None
        self._hf_base_password = ""
        self._hf_last_output = None

    # ------------------------------------------------------------------
    # Base-path tracking
    # ------------------------------------------------------------------

    def set_current_file(self, path: Path | None, password: str = "") -> None:
        """
        Aggiorna il base-path solo quando il path NON è l'ultimo output
        prodotto da questo pannello (preview temp). Se è il nostro temp,
        lo ignoriamo: il prossimo apply/preview ripartirà dal documento pulito.
        """
        if path != self._hf_last_output:
            self._hf_base_path = path
            self._hf_base_password = password
        super().set_current_file(path, password)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_content(self) -> None:
        hint = QLabel(
            "Variabili disponibili: {page}  {total}  {date}  {title}  {author}",
            self,
        )
        hint.setObjectName("hintLabel")
        self._content_layout.addWidget(hint)

        # Opzioni di differenziazione
        self._diff_first_page_cb = QCheckBox("Prima pagina diversa", self)
        self._diff_odd_even_cb = QCheckBox("Pagine pari/dispari diverse", self)
        self._content_layout.addWidget(self._diff_first_page_cb)
        self._content_layout.addWidget(self._diff_odd_even_cb)

        # --- Sezione principale: Tutte le pagine / Pagine dispari ---
        self._main_group = QGroupBox("Tutte le pagine", self)
        main_vbox = QVBoxLayout(self._main_group)
        main_vbox.setSpacing(6)
        main_vbox.setContentsMargins(8, 8, 8, 8)

        h_grp, self._h_left, self._h_center, self._h_right = _make_hf_group(
            "Intestazione", self._main_group
        )
        f_grp, self._f_left, self._f_center, self._f_right = _make_hf_group(
            "Piè di pagina", self._main_group
        )
        main_vbox.addWidget(h_grp)
        main_vbox.addWidget(f_grp)
        self._content_layout.addWidget(self._main_group)

        # --- Sezione prima pagina (nascosta) ---
        self._first_page_widget = QWidget(self)
        fp_vbox = QVBoxLayout(self._first_page_widget)
        fp_vbox.setContentsMargins(0, 0, 0, 0)
        fp_vbox.setSpacing(6)

        fp_h_grp, self._fp_h_left, self._fp_h_center, self._fp_h_right = _make_hf_group(
            "Intestazione — prima pagina", self._first_page_widget
        )
        fp_f_grp, self._fp_f_left, self._fp_f_center, self._fp_f_right = _make_hf_group(
            "Piè di pagina — prima pagina", self._first_page_widget
        )
        fp_vbox.addWidget(fp_h_grp)
        fp_vbox.addWidget(fp_f_grp)
        self._first_page_widget.setVisible(False)
        self._content_layout.addWidget(self._first_page_widget)

        # --- Sezione pagine pari (nascosta) ---
        self._even_widget = QWidget(self)
        ev_vbox = QVBoxLayout(self._even_widget)
        ev_vbox.setContentsMargins(0, 0, 0, 0)
        ev_vbox.setSpacing(6)

        ev_h_grp, self._ev_h_left, self._ev_h_center, self._ev_h_right = _make_hf_group(
            "Intestazione — pagine pari", self._even_widget
        )
        ev_f_grp, self._ev_f_left, self._ev_f_center, self._ev_f_right = _make_hf_group(
            "Piè di pagina — pagine pari", self._even_widget
        )
        ev_vbox.addWidget(ev_h_grp)
        ev_vbox.addWidget(ev_f_grp)
        self._even_widget.setVisible(False)
        self._content_layout.addWidget(self._even_widget)

        # --- Stile ---
        style_group = QGroupBox("Stile", self)
        s_form = QFormLayout(style_group)
        self._font_size_spin = QSpinBox(style_group)
        self._font_size_spin.setObjectName("formSpin")
        self._font_size_spin.setRange(6, 24)
        self._font_size_spin.setValue(9)
        self._font_size_spin.setSuffix(" pt")
        s_form.addRow("Dimensione font:", self._font_size_spin)
        self._content_layout.addWidget(style_group)

        # --- Pulsante di rimozione ---
        remove_row = QHBoxLayout()
        self._remove_btn = QPushButton("Rimuovi intestazioni/piè di pagina", self)
        self._remove_btn.setObjectName("removeButton")
        self._remove_btn.setToolTip(
            "Svuota tutti i campi e mostra l'anteprima senza intestazioni/piè di pagina.\n"
            "Nota: rimuove solo dalla sessione corrente; i PDF già salvati non vengono modificati."
        )
        self._remove_btn.setMinimumHeight(32)
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)
        remove_row.addWidget(self._remove_btn)
        self._content_layout.addLayout(remove_row)

        # Connessioni checkbox
        self._diff_first_page_cb.toggled.connect(self._on_first_page_toggled)
        self._diff_odd_even_cb.toggled.connect(self._on_odd_even_toggled)

    # ------------------------------------------------------------------
    # Slot checkbox
    # ------------------------------------------------------------------

    @pyqtSlot(bool)
    def _on_first_page_toggled(self, checked: bool) -> None:
        self._first_page_widget.setVisible(checked)

    @pyqtSlot(bool)
    def _on_odd_even_toggled(self, checked: bool) -> None:
        self._even_widget.setVisible(checked)
        self._main_group.setTitle("Pagine dispari" if checked else "Tutte le pagine")

    # ------------------------------------------------------------------
    # Rimozione intestazioni/piè di pagina
    # ------------------------------------------------------------------

    def _on_remove(self) -> None:
        """
        Svuota tutti i campi di testo, deseleziona i checkbox e lancia
        immediatamente l'anteprima: poiché nessun campo ha contenuto,
        add_headers_footers esegue una copia-passthrough dal base-path,
        mostrando il documento originale senza nessuna intestazione/piè.
        """
        self._clear_all_fields()
        self._on_preview()  # eredita da BasePanelWidget

    def _clear_all_fields(self) -> None:
        """Svuota tutti i campi di testo e deseleziona i checkbox."""
        for field in (
            self._h_left,
            self._h_center,
            self._h_right,
            self._f_left,
            self._f_center,
            self._f_right,
            self._fp_h_left,
            self._fp_h_center,
            self._fp_h_right,
            self._fp_f_left,
            self._fp_f_center,
            self._fp_f_right,
            self._ev_h_left,
            self._ev_h_center,
            self._ev_h_right,
            self._ev_f_left,
            self._ev_f_center,
            self._ev_f_right,
        ):
            field.clear()
        self._diff_first_page_cb.setChecked(False)
        self._diff_odd_even_cb.setChecked(False)

    # ------------------------------------------------------------------
    # Abilita/disabilita pulsante rimozione insieme agli altri
    # ------------------------------------------------------------------

    def _on_file_changed(self, path: Path | None) -> None:
        self._remove_btn.setEnabled(path is not None)

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def _collect_config_impl(self) -> HeaderFooterConfig:
        diff_first = self._diff_first_page_cb.isChecked()
        diff_odd_even = self._diff_odd_even_cb.isChecked()

        return HeaderFooterConfig(
            header=HeaderFooterSection(
                left=self._h_left.text(),
                center=self._h_center.text(),
                right=self._h_right.text(),
            ),
            footer=HeaderFooterSection(
                left=self._f_left.text(),
                center=self._f_center.text(),
                right=self._f_right.text(),
            ),
            font_size=self._font_size_spin.value(),
            different_first_page=diff_first,
            different_odd_even=diff_odd_even,
            first_page_header=HeaderFooterSection(
                left=self._fp_h_left.text(),
                center=self._fp_h_center.text(),
                right=self._fp_h_right.text(),
            )
            if diff_first
            else HeaderFooterSection(),
            first_page_footer=HeaderFooterSection(
                left=self._fp_f_left.text(),
                center=self._fp_f_center.text(),
                right=self._fp_f_right.text(),
            )
            if diff_first
            else HeaderFooterSection(),
            even_header=HeaderFooterSection(
                left=self._ev_h_left.text(),
                center=self._ev_h_center.text(),
                right=self._ev_h_right.text(),
            )
            if diff_odd_even
            else HeaderFooterSection(),
            even_footer=HeaderFooterSection(
                left=self._ev_f_left.text(),
                center=self._ev_f_center.text(),
                right=self._ev_f_right.text(),
            )
            if diff_odd_even
            else HeaderFooterSection(),
        )

    def _run_core(self, input_path: Path, output_path: Path, password: str, config) -> Path:
        from core.headers_footers import add_headers_footers

        # Usa sempre il base-path (documento pulito prima di qualsiasi H/F).
        # Fallback su input_path se base-path non è disponibile (caso anomalo).
        actual_input = self._hf_base_path if self._hf_base_path is not None else input_path
        actual_pwd = self._hf_base_password if self._hf_base_path is not None else password
        add_headers_footers(actual_input, output_path, config, password=actual_pwd or None)
        return output_path

    # ------------------------------------------------------------------
    # Tracciamento ultimo output (solo preview con successo)
    # ------------------------------------------------------------------

    @pyqtSlot(Path)
    def _on_preview_done(self, tmp_path: Path) -> None:
        # Registra il temp SOLO se il file esiste ed è valido (successo).
        # Se il file è vuoto/assente, super() lo elimina e non emette il segnale:
        # _hf_last_output rimane al valore precedente, il che è corretto.
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            self._hf_last_output = tmp_path
        super()._on_preview_done(tmp_path)


# ---------------------------------------------------------------------------
# Helper di modulo
# ---------------------------------------------------------------------------


def _make_hf_group(
    title: str, parent: QWidget
) -> tuple[QGroupBox, QLineEdit, QLineEdit, QLineEdit]:
    """Crea un QGroupBox con campi sinistra/centro/destra e li restituisce."""
    group = QGroupBox(title, parent)
    form = QFormLayout(group)
    left = QLineEdit(group)
    left.setPlaceholderText("Sinistra")
    center = QLineEdit(group)
    center.setPlaceholderText("Centro")
    right = QLineEdit(group)
    right.setPlaceholderText("Destra")
    form.addRow("Sinistra:", left)
    form.addRow("Centro:", center)
    form.addRow("Destra:", right)
    return group, left, center, right
