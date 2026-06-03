from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from utils.exceptions import InvalidPageRangeError
from utils.page_range_parser import parse_page_ranges


class PageRangeInput(QWidget):
    """
    Campo di testo validato per range di pagine (es. "1-3, 5, 7-9").

    Emette:
        range_changed(list[tuple[int,int]]): quando il range è valido e cambia.
        range_invalid(str): messaggio di errore quando il range non è valido.
    """

    range_changed = pyqtSignal(list)
    range_invalid = pyqtSignal(str)

    def __init__(
        self,
        placeholder: str = "es. 1-3, 5, 7-9",
        total_pages: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._total_pages = total_pages
        self._valid = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(placeholder)
        self._edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._edit)

        self._error_label = QLabel(self)
        self._error_label.setObjectName("hintLabel")
        self._error_label.setStyleSheet("color: #B5383A; font-size: 11px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_total_pages(self, total: int | None) -> None:
        self._total_pages = total
        self._on_text_changed(self._edit.text())

    def text(self) -> str:
        return self._edit.text()

    def set_text(self, text: str) -> None:
        self._edit.setText(text)

    def is_valid(self) -> bool:
        return self._valid

    def get_ranges(self) -> list[tuple[int, int]] | None:
        """Ritorna il range parsato se valido, altrimenti None."""
        try:
            return parse_page_ranges(self._edit.text(), self._total_pages)
        except InvalidPageRangeError:
            return None

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_text_changed(self, text: str) -> None:
        text = text.strip()
        if not text:
            self._set_valid(True)
            self._error_label.setVisible(False)
            return

        try:
            ranges = parse_page_ranges(text, self._total_pages)
            self._set_valid(True)
            self._error_label.setVisible(False)
            self.range_changed.emit(ranges)
        except InvalidPageRangeError as exc:
            self._set_valid(False)
            self._error_label.setText(str(exc))
            self._error_label.setVisible(True)
            self.range_invalid.emit(str(exc))

    def _set_valid(self, valid: bool) -> None:
        self._valid = valid
        self._edit.setProperty("invalid", not valid)
        self._edit.style().unpolish(self._edit)
        self._edit.style().polish(self._edit)
