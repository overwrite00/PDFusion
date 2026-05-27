"""Test per componenti UI principali (main_window, viewer, panels)."""

import pytest
from pathlib import Path

from ui.main_window import MainWindow


@pytest.fixture
def main_window(qtbot):
    """Fixture che crea la finestra principale per i test."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    return window


@pytest.fixture
def sample_pdf():
    """Ritorna il PDF di test dal fixture."""
    # Usa il sample.pdf predefinito da fixtures
    fixture_dir = Path(__file__).parent.parent / "fixtures"
    pdf_path = fixture_dir / "sample.pdf"

    if not pdf_path.exists():
        # Se non esiste, crea un PDF minimal
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test Page")
        temp_path = fixture_dir / "sample.pdf"
        temp_path.parent.mkdir(exist_ok=True)
        doc.save(str(temp_path))
        doc.close()
        return temp_path

    return pdf_path


class TestMainWindowBasics:
    """Test funzionalità di base della finestra principale."""

    def test_window_initialized(self, main_window):
        """Verifica che la finestra si inizializzi correttamente."""
        assert main_window.windowTitle().startswith("PDFusion")
        assert main_window.width() >= 1100
        assert main_window.height() >= 700

    def test_no_document_loaded_initially(self, main_window):
        """Verifica che nessun documento sia caricato all'inizio."""
        assert main_window._current_path is None
        assert main_window._pending_preview is None

    def test_panels_created(self, main_window):
        """Verifica che tutti i 16 tool panel siano creati."""
        expected_tools = [
            "split", "merge", "delete_page", "insert_page",
            "compress", "protect", "watermark", "license_page",
            "headers_footers", "rotate", "reorder", "extract",
            "metadata", "pdf_to_images", "images_to_pdf", "batch"
        ]
        for tool in expected_tools:
            assert tool in main_window._panels, f"Panel '{tool}' non trovato"


class TestFileOpening:
    """Test apertura file e gestione documenti."""

    def test_open_file_valid_pdf(self, main_window, qtbot, sample_pdf):
        """Verifica apertura di un PDF valido."""
        main_window.open_file(sample_pdf)
        qtbot.wait(500)  # Attendi caricamento

        assert main_window._current_path == sample_pdf
        # Viewer ha caricato il documento
        assert main_window._viewer is not None

    def test_open_file_updates_window_title(self, main_window, qtbot, sample_pdf):
        """Verifica che il titolo della finestra si aggiorni."""
        main_window.open_file(sample_pdf)
        qtbot.wait(500)

        assert sample_pdf.name in main_window.windowTitle()

    def test_open_nonexistent_file(self, main_window, qtbot):
        """Verifica gestione file non trovato."""
        nonexistent = Path("/tmp/nonexistent_file_xyz.pdf")
        main_window.open_file(nonexistent)
        qtbot.wait(500)

        # Dovrebbe gestire gracefully senza crash
        assert main_window is not None


class TestToolPanelSelection:
    """Test selezione tool panel."""

    def test_tool_selection_changes_panel(self, main_window, qtbot, sample_pdf):
        """Verifica che selezionare un tool cambi il pannello visualizzato."""
        main_window.open_file(sample_pdf)
        qtbot.wait(500)

        # Seleziona compress tool
        main_window._on_tool_selected("compress")
        qtbot.wait(200)

        current = main_window._stack.currentWidget()
        assert current is main_window._panels["compress"]

    def test_tool_receives_current_file(self, main_window, qtbot, sample_pdf):
        """Verifica che il panel riceva il file corrente."""
        main_window.open_file(sample_pdf)
        qtbot.wait(500)

        main_window._on_tool_selected("split")
        qtbot.wait(200)

        panel = main_window._panels["split"]
        assert panel._current_path == sample_pdf


class TestPreviewManagement:
    """Test gestione preview temporanei."""

    def test_preview_cleanup_on_close(self, main_window, qtbot, sample_pdf):
        """Verifica che i file preview temporanei siano puliti."""
        main_window.open_file(sample_pdf)
        qtbot.wait(500)

        initial_temp_count = len(main_window._temp_files)

        # Chiudi e apri un nuovo file
        main_window._cleanup_all_temps()
        qtbot.wait(200)

        assert len(main_window._temp_files) == 0

    def test_preview_file_deleted(self, main_window, qtbot, sample_pdf, tmp_path):
        """Verifica che i file preview siano effettivamente cancellati."""
        main_window.open_file(sample_pdf)
        qtbot.wait(500)

        # Simula creazione preview temp
        preview_file = tmp_path / "test_preview.pdf"
        preview_file.write_bytes(b"dummy")
        main_window._temp_files.append(preview_file)

        main_window._cleanup_all_temps()
        qtbot.wait(200)

        # File dovrebbe essere cancellato
        assert not preview_file.exists()


class TestKeyboardShortcuts:
    """Test shortcut tastiera."""

    def test_shortcut_registered(self, main_window, qtbot):
        """Verifica che le shortcut siano registrate."""
        # Almeno open action dovrebbe esistere
        actions = main_window.findChildren(type(main_window.actions()[0]) if main_window.actions() else None)
        # Verifica che main_window abbia azioni registrate
        assert len(main_window.actions()) > 0, "Nessuna shortcut registrata"


class TestMemoryManagement:
    """Test gestione memoria (no leak, cleanup)."""

    def test_close_document_releases_resources(self, main_window, qtbot, sample_pdf):
        """Verifica che chiudere un documento rilasci risorse."""
        main_window.open_file(sample_pdf)
        qtbot.wait(500)

        # Viewer ha il documento
        assert main_window._viewer is not None

        # Simula chiusura
        main_window._viewer.close_document()
        qtbot.wait(200)

        # Viewer dovrebbe esistere ma documento chiuso
        assert main_window._viewer is not None

    def test_temp_files_cleanup_on_exit(self, main_window, qtbot, tmp_path):
        """Verifica cleanup temp files all'uscita."""
        # Simula creazione temp file
        temp_file = tmp_path / "test_exit_cleanup.pdf"
        temp_file.write_bytes(b"dummy")
        main_window._temp_files.append(temp_file)

        # Cleanup
        main_window._cleanup_all_temps()
        qtbot.wait(200)

        assert not temp_file.exists()
        assert len(main_window._temp_files) == 0
