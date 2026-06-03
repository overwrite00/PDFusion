"""Tests for PreviewRenderer."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QCoreApplication  # noqa: I001

from conftest import is_headless_environment
from ui.panels.preview_renderer import PreviewRenderer


@pytest.fixture
def qapp():
    """Provide QApplication for Qt tests."""
    # Skip test if running in headless environment (CI without display)
    if is_headless_environment():
        pytest.skip("QApplication not supported in headless environment")

    app = QCoreApplication.instance()
    if app is None:
        try:
            app = QCoreApplication([])
        except Exception as e:
            pytest.skip(f"QApplication initialization failed: {e}")
    yield app


@pytest.fixture
def temp_pdf(tmp_path):
    """Create a temporary PDF file."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("dummy pdf content")
    return pdf_path


@pytest.fixture
def mock_render_fn():
    """Create a mock render function."""
    return MagicMock()


class TestPreviewRenderer:
    """Test PreviewRenderer functionality."""

    def test_initialization(self, qapp):
        """Test PreviewRenderer initializes correctly."""
        renderer = PreviewRenderer()
        assert renderer is not None
        assert not renderer.is_rendering()
        assert renderer._preview_tmp is None

    def test_is_rendering_initial(self, qapp):
        """Test is_rendering is False initially."""
        renderer = PreviewRenderer()
        assert not renderer.is_rendering()

    def test_render_preview_creates_temp_file(self, qapp, temp_pdf, mock_render_fn):
        """Test render_preview creates a temporary file."""
        renderer = PreviewRenderer()
        mock_render_fn.return_value = Path()

        tmp_path = renderer.render_preview(
            mock_render_fn,
            temp_pdf,
            config=None,
            password="",
        )

        assert tmp_path is not None
        assert tmp_path.name.startswith(".pdfusion_preview_")
        assert tmp_path.suffix == ".pdf"

        # Cleanup thread
        renderer.cancel_render()

    def test_render_preview_returns_none_when_rendering(self, qapp, temp_pdf, mock_render_fn):
        """Test render_preview returns None when already rendering."""
        renderer = PreviewRenderer()
        mock_render_fn.return_value = Path()

        # Start first render
        tmp_path1 = renderer.render_preview(
            mock_render_fn,
            temp_pdf,
            config=None,
            password="",
        )
        assert tmp_path1 is not None
        assert renderer.is_rendering()

        # Try to start second render while first is in progress
        tmp_path2 = renderer.render_preview(
            mock_render_fn,
            temp_pdf,
            config=None,
            password="",
        )
        assert tmp_path2 is None

        # Cleanup
        renderer.cancel_render()

    def test_preview_ready_signal(self, qapp, tmp_path):
        """Test preview_ready signal is emitted on success."""
        renderer = PreviewRenderer()
        signal_spy = MagicMock()
        renderer.preview_ready.connect(signal_spy)

        # Create a valid temp file
        tmp_file = tmp_path / "preview.pdf"
        tmp_file.write_text("PDF content")

        # Manually call the finished handler to simulate successful render
        renderer._preview_tmp = tmp_file
        renderer._on_render_finished(tmp_file)

        signal_spy.assert_called_once()
        # Signal should emit the preview path
        assert signal_spy.call_args[0][0] == tmp_file
        # File should be cleared
        assert renderer._preview_tmp is None

    def test_preview_failed_signal(self, qapp):
        """Test preview_failed signal is emitted on error."""
        renderer = PreviewRenderer()
        signal_spy = MagicMock()
        renderer.preview_failed.connect(signal_spy)

        error_msg = "Test error message"
        renderer._on_render_error(error_msg)

        signal_spy.assert_called_once_with(error_msg)

    def test_cancel_render(self, qapp, temp_pdf, mock_render_fn):
        """Test cancelling a render."""
        renderer = PreviewRenderer()
        mock_render_fn.return_value = Path()

        tmp_path = renderer.render_preview(
            mock_render_fn,
            temp_pdf,
            config=None,
            password="",
        )
        assert tmp_path is not None
        assert renderer.is_rendering()

        renderer.cancel_render()
        assert not renderer.is_rendering()
        assert renderer._preview_tmp is None

    def test_cleanup_temp_file(self, qapp):
        """Test temporary file cleanup."""
        renderer = PreviewRenderer()

        # Create a temp file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_file = Path(tmp.name)

        renderer._preview_tmp = tmp_file
        assert tmp_file.exists()

        renderer._cleanup_temp_file()

        # File should be deleted
        assert not tmp_file.exists()
        assert renderer._preview_tmp is None

    def test_render_preview_temp_in_same_dir(self, qapp, temp_pdf, mock_render_fn):
        """Test that temp files are created in same directory as input."""
        renderer = PreviewRenderer()
        mock_render_fn.return_value = Path()

        tmp_path = renderer.render_preview(
            mock_render_fn,
            temp_pdf,
            config=None,
            password="",
        )

        # Temp file should be in same directory as input
        assert tmp_path.parent == temp_pdf.parent

        # Cleanup
        renderer.cancel_render()

    def test_empty_file_handling(self, qapp, tmp_path):
        """Test handling of empty result files."""
        renderer = PreviewRenderer()
        signal_spy = MagicMock()
        renderer.preview_failed.connect(signal_spy)

        # Create an empty temp file
        empty_file = tmp_path / "empty.pdf"
        empty_file.write_text("")

        renderer._preview_tmp = empty_file
        renderer._on_render_finished(empty_file)

        signal_spy.assert_called_once()
        # File should be cleaned up
        assert not empty_file.exists()

    def test_missing_file_handling(self, qapp, tmp_path):
        """Test handling of missing result files."""
        renderer = PreviewRenderer()
        signal_spy = MagicMock()
        renderer.preview_failed.connect(signal_spy)

        missing_file = tmp_path / "missing.pdf"
        renderer._preview_tmp = missing_file
        renderer._on_render_finished(missing_file)

        signal_spy.assert_called_once()
