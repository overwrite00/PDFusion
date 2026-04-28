from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QFileDialog, QLabel, QVBoxLayout, QWidget


class DropZone(QWidget):
    """
    Area drag-drop per accettare file PDF.
    Emette files_dropped(list[Path]) quando i file vengono rilasciati.
    Clic singolo apre il dialog di selezione file.
    """

    files_dropped = pyqtSignal(list)  # list[Path]

    def __init__(
        self,
        accept_extensions: tuple[str, ...] = (".pdf",),
        label_text: str = "Trascina qui i file PDF\no clicca per selezionarli",
        multiple: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accept_ext = accept_extensions
        self._multiple = multiple
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(label_text, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setObjectName("hintLabel")
        layout.addWidget(self._label)

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
            if any(p.suffix.lower() in self._accept_ext for p in paths):
                event.acceptProposedAction()
                self.setProperty("dragging", True)
                self.style().unpolish(self)
                self.style().polish(self)
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)

        paths = [
            Path(u.toLocalFile())
            for u in event.mimeData().urls()
            if Path(u.toLocalFile()).suffix.lower() in self._accept_ext
        ]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Click → dialog selezione
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_file_dialog()

    def _open_file_dialog(self) -> None:
        ext_filter = "PDF (*.pdf)" if ".pdf" in self._accept_ext else "File (*.*)"
        if self._multiple:
            paths, _ = QFileDialog.getOpenFileNames(self, "Seleziona file", "", ext_filter)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Seleziona file", "", ext_filter)
            paths = [path] if path else []

        if paths:
            self.files_dropped.emit([Path(p) for p in paths])

    def set_label(self, text: str) -> None:
        self._label.setText(text)
