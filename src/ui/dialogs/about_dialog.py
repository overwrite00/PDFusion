from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from utils.config import APP_NAME, VERSION


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Informazioni su {APP_NAME}")
        self.setMinimumWidth(360)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(10)

        title = QLabel(f"<b style='font-size:18px;color:#4A6FA5'>{APP_NAME}</b>", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_lbl = QLabel(f"Versione {VERSION}", self)
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_lbl.setObjectName("hintLabel")
        layout.addWidget(version_lbl)

        layout.addSpacing(8)

        desc = QLabel(
            "Gestione PDF cross-platform: unisci, dividi, comprimi,\n"
            "proteggi, aggiungi watermark e molto altro.",
            self,
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        license_lbl = QLabel(
            "Licenza: <a href='https://opensource.org/licenses/MIT'>MIT</a>",
            self,
        )
        license_lbl.setOpenExternalLinks(True)
        license_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
