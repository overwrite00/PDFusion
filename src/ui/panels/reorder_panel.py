from pathlib import Path

from PyQt6.QtWidgets import QLabel, QWidget

from ui.panels.base_panel import BasePanelWidget


class ReorderPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Riordina pagine", parent)
        self._new_order: list[int] | None = None
        self._setup_content()

    def _setup_content(self) -> None:
        hint = QLabel(
            "Trascina le miniature nella striscia in basso per riordinare le pagine.\n"
            "Il nuovo ordine verrà applicato quando clicchi Applica.",
            self,
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        self._content_layout.addWidget(hint)

    def apply_order(self, new_order: list[int], path: Path, password: str) -> None:
        """Chiamato da MainWindow quando il thumbnail panel emette order_changed."""
        self._new_order = new_order
        self._current_path = path
        self._current_password = password

    def _collect_config(self):
        if not self._new_order:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Nessun riordino",
                "Trascina le miniature per cambiare l'ordine delle pagine.",
            )
            return None
        return {"order": self._new_order}

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.reorder import reorder_pages

        reorder_pages(input_path, config["order"], output_path, password or None)
        return output_path
