from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.config import APP_NAME
from utils.update_checker import ReleaseInfo, pick_asset_url


class UpdateAvailableDialog(QDialog):
    """Mostra la release più recente disponibile per il canale corrente
    (stable o beta) e permette di scaricarla senza uscire dal programma."""

    def __init__(
        self, release: ReleaseInfo, current_version: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._release = release
        self._skip_requested = False
        self.setWindowTitle("Aggiornamento disponibile")
        self.setMinimumWidth(420)
        self._setup_ui(current_version)

    def _setup_ui(self, current_version: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(10)

        title = QLabel(
            "<b style='font-size:16px;color:#4A6FA5'>Nuova versione disponibile</b>", self
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel(
            f"{APP_NAME} {self._release.tag.lstrip('vV')} è disponibile "
            f"(versione attuale: {current_version}).",
            self,
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        notes_text = self._release.body.strip()
        if notes_text:
            layout.addSpacing(6)
            notes = QPlainTextEdit(self)
            notes.setReadOnly(True)
            notes.setPlainText(notes_text)
            notes.setMaximumHeight(160)
            layout.addWidget(notes)

        layout.addSpacing(8)

        buttons = QDialogButtonBox(parent=self)
        download_btn = buttons.addButton("Scarica", QDialogButtonBox.ButtonRole.AcceptRole)
        skip_btn = buttons.addButton(
            "Ignora questa versione", QDialogButtonBox.ButtonRole.DestructiveRole
        )
        later_btn = buttons.addButton("Più tardi", QDialogButtonBox.ButtonRole.RejectRole)

        download_btn.clicked.connect(self._on_download)
        skip_btn.clicked.connect(self._on_skip)
        later_btn.clicked.connect(self.reject)

        layout.addWidget(buttons)

    def _on_download(self) -> None:
        # Apre direttamente l'asset dell'installer per il sistema operativo
        # corrente (se pubblicato con la release), altrimenti la pagina della
        # release su GitHub. Il download avviene nel browser di sistema:
        # PDFusion non scarica né esegue nulla in autonomia.
        asset_url = pick_asset_url(self._release.assets)
        QDesktopServices.openUrl(QUrl(asset_url or self._release.url))
        self.accept()

    def _on_skip(self) -> None:
        self._skip_requested = True
        self.reject()

    def skip_requested(self) -> bool:
        return self._skip_requested
