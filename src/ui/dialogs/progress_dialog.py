from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ProgressDialog(QDialog):
    """
    Dialog modale di avanzamento per operazioni lunghe.
    Riceve aggiornamenti via slot update_progress(completati, totale, descrizione).
    Emette cancelled() se l'utente clicca Annulla.
    """

    cancelled = pyqtSignal()

    def __init__(
        self,
        title: str = "Elaborazione in corso…",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(True)
        self.setMinimumWidth(380)
        self._cancelled = False
        self._setup_ui(title)

    def _setup_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("panelTitle")
        layout.addWidget(self._title_label)

        self._desc_label = QLabel("Preparazione…", self)
        self._desc_label.setObjectName("hintLabel")
        self._desc_label.setWordWrap(True)
        layout.addWidget(self._desc_label)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._count_label = QLabel("", self)
        self._count_label.setObjectName("hintLabel")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._count_label)

        self._cancel_btn = QPushButton("Annulla", self)
        self._cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_progress(self, completed: int, total: int, description: str) -> None:
        """Aggiorna la barra e il testo. Thread-safe via Qt event queue."""
        if total > 0:
            pct = int(completed / total * 100)
            self._progress.setValue(pct)
            self._count_label.setText(f"{completed} / {total}")
        self._desc_label.setText(description)

    def set_indeterminate(self) -> None:
        """Modalità indeterminata per operazioni di durata sconosciuta."""
        self._progress.setRange(0, 0)

    def is_cancelled(self) -> bool:
        return self._cancelled

    def finish(self) -> None:
        self._progress.setValue(100)
        self.accept()

    # ------------------------------------------------------------------

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._cancel_btn.setEnabled(False)
        self._desc_label.setText("Annullamento in corso…")
        self.cancelled.emit()
