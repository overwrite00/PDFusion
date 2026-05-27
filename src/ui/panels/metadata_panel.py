from pathlib import Path

from PyQt6.QtWidgets import QFormLayout, QLabel, QLineEdit, QWidget

from core.metadata import PDFMetadata
from ui.panels.base_panel import BasePanelWidget


class MetadataPanel(BasePanelWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Metadati PDF", parent)
        self._setup_content()

    def _setup_content(self) -> None:
        hint = QLabel(
            "I campi lasciati vuoti non verranno modificati.\n"
            "Inserisci uno spazio per cancellare un campo esistente.",
            self,
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        self._content_layout.addWidget(hint)

        form = QFormLayout()
        self._title = QLineEdit(self)
        self._author = QLineEdit(self)
        self._subject = QLineEdit(self)
        self._keywords = QLineEdit(self)
        self._creator = QLineEdit(self)
        form.addRow("Titolo:", self._title)
        form.addRow("Autore:", self._author)
        form.addRow("Oggetto:", self._subject)
        form.addRow("Parole chiave:", self._keywords)
        form.addRow("Applicazione:", self._creator)
        self._content_layout.addLayout(form)

    def _on_file_changed(self, path: Path | None) -> None:
        if not path:
            return
        try:
            from core.metadata import read_metadata

            meta = read_metadata(path, self._current_password or None)
            self._title.setText(meta.title or "")
            self._author.setText(meta.author or "")
            self._subject.setText(meta.subject or "")
            self._keywords.setText(meta.keywords or "")
            self._creator.setText(meta.creator or "")
        except Exception:
            pass

    def _collect_config(self) -> PDFMetadata:
        def _val(edit: QLineEdit) -> str | None:
            t = edit.text()
            if not t:
                return None  # non toccare
            return "" if t.strip() == "" else t  # spazio = cancella

        return PDFMetadata(
            title=_val(self._title),
            author=_val(self._author),
            subject=_val(self._subject),
            keywords=_val(self._keywords),
            creator=_val(self._creator),
        )

    def _run_core(self, input_path, output_path, password, config) -> Path:
        from core.metadata import write_metadata

        write_metadata(input_path, config, output_path, password or None)
        return output_path
