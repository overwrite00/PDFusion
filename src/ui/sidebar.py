from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class SidebarItem:
    key: str
    label: str
    is_separator: bool = False


SIDEBAR_ITEMS: list[SidebarItem] = [
    SidebarItem("split", "✂  Dividi PDF"),
    SidebarItem("merge", "🔗  Unisci PDF"),
    SidebarItem("delete_page", "🗑  Elimina pagina"),
    SidebarItem("insert_page", "➕  Inserisci pagina"),
    SidebarItem("sep1", "", is_separator=True),
    SidebarItem("compress", "⚡  Comprimi"),
    SidebarItem("protect", "🔒  Proteggi"),
    SidebarItem("watermark", "💧  Watermark"),
    SidebarItem("license_page", "📜  Pagina licenza"),
    SidebarItem("headers_footers", "📄  Intestazioni / Piè"),
    SidebarItem("sep2", "", is_separator=True),
    SidebarItem("rotate", "🔄  Ruota pagine"),
    SidebarItem("reorder", "↕  Riordina pagine"),
    SidebarItem("extract", "📤  Estrai pagine"),
    SidebarItem("metadata", "🏷  Metadati"),
    SidebarItem("sep3", "", is_separator=True),
    SidebarItem("pdf_to_images", "🖼  PDF → Immagini"),
    SidebarItem("images_to_pdf", "📁  Immagini → PDF"),
    SidebarItem("sep4", "", is_separator=True),
    SidebarItem("batch", "⚙  Batch"),
]


class Sidebar(QWidget):
    """
    Barra laterale sinistra con la lista degli strumenti.
    Emette tool_selected(str) quando l'utente seleziona uno strumento.
    Emette quit_requested() quando l'utente clicca "Esci".
    """

    tool_selected = pyqtSignal(str)
    quit_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(200)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo / titolo
        header = QWidget(self)
        header.setFixedHeight(48)
        header.setStyleSheet("background:#4A6FA5; border-bottom:1px solid #3A5A8C;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 0, 0)
        logo = QLabel("PDFusion", header)
        logo.setStyleSheet("color:#FFFFFF; font-size:17px; font-weight:700;")
        h_layout.addWidget(logo)
        layout.addWidget(header)

        # Lista strumenti
        self._list = QListWidget(self)
        self._list.setObjectName("sidebar")
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        self._key_map: dict[int, str] = {}
        row = 0
        for item_def in SIDEBAR_ITEMS:
            if item_def.is_separator:
                from PyQt6.QtCore import QSize

                sep = QListWidgetItem("")
                sep.setFlags(Qt.ItemFlag.NoItemFlags)
                sep.setSizeHint(QSize(0, 8))
                self._list.addItem(sep)
            else:
                w_item = QListWidgetItem(item_def.label)
                self._list.addItem(w_item)
                self._key_map[row] = item_def.key
            row += 1

        # Footer: pulsante Esci
        footer = QWidget(self)
        footer.setObjectName("sidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(8, 6, 8, 10)
        footer_layout.setSpacing(0)

        quit_btn = QPushButton("Esci", footer)
        quit_btn.setObjectName("sidebarQuitButton")
        quit_btn.setFixedHeight(34)
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self.quit_requested)
        footer_layout.addWidget(quit_btn)
        layout.addWidget(footer)

    def select_tool(self, key: str) -> None:
        for row, k in self._key_map.items():
            if k == key:
                self._list.setCurrentRow(row)
                return

    def _on_row_changed(self, row: int) -> None:
        key = self._key_map.get(row)
        if key:
            self.tool_selected.emit(key)
