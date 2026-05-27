from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.protect import EncryptionLevel, ProtectConfig
from ui.panels.base_panel import BasePanelWidget


class ProtectPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Proteggi PDF", parent)
        # L'anteprima di un PDF cifrato con user_password non può essere
        # visualizzata nel viewer (richiederebbe la password per aprirla).
        # Disabilitiamo il pulsante Anteprima per questo pannello.
        self._supports_preview = False
        self._setup_content()

    def _setup_content(self) -> None:
        pwd_group = QGroupBox("Password", self)
        form = QFormLayout(pwd_group)

        self._user_pwd = QLineEdit(pwd_group)
        self._user_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._user_pwd.setPlaceholderText("Password per aprire il documento")
        form.addRow("Password utente:", self._user_pwd)

        self._owner_pwd = QLineEdit(pwd_group)
        self._owner_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._owner_pwd.setPlaceholderText("Password per modificare i permessi")
        form.addRow("Password proprietario:", self._owner_pwd)

        hint = QLabel(
            "Se lasci vuota la password utente, il documento si apre "
            "liberamente ma le restrizioni vengono comunque applicate.",
            pwd_group,
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        form.addRow(hint)

        self._content_layout.addWidget(pwd_group)

        # Permessi
        perm_group = QGroupBox("Restrizioni", self)
        perm_layout = QVBoxLayout(perm_group)

        self._allow_print = QCheckBox("Consenti stampa", perm_group)
        self._allow_print.setChecked(True)
        self._allow_highres = QCheckBox("Consenti stampa alta risoluzione", perm_group)
        self._allow_highres.setChecked(True)
        self._allow_copy = QCheckBox("Consenti copia testo", perm_group)
        self._allow_edit = QCheckBox("Consenti modifica contenuto", perm_group)
        self._allow_annot = QCheckBox("Consenti annotazioni", perm_group)
        self._allow_forms = QCheckBox("Consenti compilazione moduli", perm_group)

        for cb in [
            self._allow_print,
            self._allow_highres,
            self._allow_copy,
            self._allow_edit,
            self._allow_annot,
            self._allow_forms,
        ]:
            perm_layout.addWidget(cb)

        self._content_layout.addWidget(perm_group)

        # Crittografia
        enc_group = QGroupBox("Livello di crittografia", self)
        enc_form = QFormLayout(enc_group)
        self._enc_combo = QComboBox(enc_group)
        self._enc_combo.setObjectName("formCombo")
        self._enc_combo.addItem("AES-128 bit  ✓ consigliato", EncryptionLevel.AES_128)
        self._enc_combo.addItem("AES-256 bit (richiede Acrobat 9+)", EncryptionLevel.AES_256)
        enc_form.addRow("Crittografia:", self._enc_combo)
        self._content_layout.addWidget(enc_group)

    def _collect_config(self) -> ProtectConfig:
        return ProtectConfig(
            user_password=self._user_pwd.text(),
            owner_password=self._owner_pwd.text(),
            encryption=self._enc_combo.currentData(),
            allow_print=self._allow_print.isChecked(),
            allow_print_highres=self._allow_highres.isChecked(),
            allow_copy=self._allow_copy.isChecked(),
            allow_edit=self._allow_edit.isChecked(),
            allow_annotations=self._allow_annot.isChecked(),
            allow_forms=self._allow_forms.isChecked(),
        )

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.protect import protect

        protect(input_path, output_path, config, password or None)
        return output_path
