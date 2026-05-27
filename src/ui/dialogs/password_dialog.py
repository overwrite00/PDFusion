from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class PasswordDialog(QDialog):
    """Dialog per inserimento password PDF."""

    def __init__(
        self,
        filename: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Password richiesta")
        self.setMinimumWidth(320)
        self._setup_ui(filename)

    def _setup_ui(self, filename: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        if filename:
            msg = f"Il file <b>{filename}</b> è protetto da password."
        else:
            msg = "Il file è protetto da password."

        label = QLabel(msg, self)
        label.setWordWrap(True)
        layout.addWidget(label)

        self._edit = QLineEdit(self)
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit.setPlaceholderText("Inserisci la password…")
        self._edit.returnPressed.connect(self._try_accept)
        layout.addWidget(self._edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _try_accept(self) -> None:
        if self._edit.text():
            self.accept()

    def password(self) -> str | None:
        """Ritorna la password inserita o None se dialog annullato."""
        return self._edit.text() if self.result() == QDialog.DialogCode.Accepted else None


def ask_password(filename: str = "", parent: QWidget | None = None) -> str | None:
    """Convenience function: mostra il dialog e restituisce la password."""
    dlg = PasswordDialog(filename, parent)
    dlg.exec()
    return dlg.password()
