from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from utils.recent_files import clear_recent_files, get_recent_files


class RecentFilesWidget(QWidget):
    """
    Pannello che mostra i file aperti di recente.
    Emette file_selected(Path) al doppio clic.
    """

    file_selected = pyqtSignal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("File recenti", self)
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self._list = QListWidget(self)
        self._list.setAlternatingRowColors(False)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        bottom = QHBoxLayout()
        self._clear_btn = QPushButton("Cancella cronologia", self)
        self._clear_btn.clicked.connect(self._on_clear)
        bottom.addStretch()
        bottom.addWidget(self._clear_btn)
        layout.addLayout(bottom)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Ricarica la lista dai file salvati su disco."""
        self._list.clear()
        paths = get_recent_files()
        if not paths:
            placeholder = QListWidgetItem("Nessun file recente")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(placeholder)
            return

        for path in paths:
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._list.addItem(item)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_double_click(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(path, Path) and path.exists():
            self.file_selected.emit(path)

    def _on_clear(self) -> None:
        clear_recent_files()
        self.refresh()
