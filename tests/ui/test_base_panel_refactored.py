"""Tests for refactored BasePanelWidget."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from ..conftest import is_headless_environment
from ui.panels.base_panel import BasePanelWidget


@pytest.fixture
def qapp():
    """Provide QApplication for Qt tests."""
    # Skip test if running in headless environment (CI without display)
    if is_headless_environment():
        pytest.skip("QApplication not supported in headless environment")

    app = QCoreApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception as e:
            pytest.skip(f"QApplication initialization failed: {e}")
    yield app


@pytest.fixture
def temp_pdf(tmp_path):
    """Create a temporary PDF file."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("dummy pdf content")
    return pdf_path


class ConcretePanel(BasePanelWidget):
    """Concrete implementation for testing."""

    def __init__(self, parent=None):
        super().__init__("Test Panel", parent)
        self.collect_config_calls = 0
        self._setup_content()

    def _setup_content(self):
        """Minimal content setup for testing."""
        pass

    def _collect_config_impl(self):
        """Return a simple test config."""
        self.collect_config_calls += 1
        return {"test": "config"}

    def _run_core(self, input_path, output_path, password, config):
        """Mock implementation that just returns the output path."""
        return output_path


class TestBasePanelWidget:
    """Test BasePanelWidget refactored functionality."""

    def test_initialization(self, qapp):
        """Test BasePanelWidget initializes with components."""
        panel = ConcretePanel()
        assert panel is not None
        assert panel._file_monitor is not None
        assert panel._preview_renderer is not None

    def test_set_current_file(self, qapp, temp_pdf):
        """Test setting the current file."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf, "password")
        assert panel._current_path == temp_pdf
        assert panel._current_password == "password"

    def test_set_current_file_none(self, qapp):
        """Test setting current file to None."""
        panel = ConcretePanel()
        panel.set_current_file(None)
        assert panel._current_path is None
        assert panel._original_stem == ""

    def test_original_stem_tracking(self, qapp, temp_pdf):
        """Test that original stem is tracked correctly."""
        panel = ConcretePanel()
        assert panel._original_stem == ""

        panel.set_current_file(temp_pdf)
        assert panel._original_stem == temp_pdf.stem

    def test_original_stem_preserved_with_preview(self, qapp, temp_pdf):
        """Test that original stem is preserved when preview temp is active."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)
        original_stem = panel._original_stem

        # Simulate preview temp activation
        preview_tmp = temp_pdf.parent / ".pdfusion_preview_xyz.pdf"
        panel.set_current_file(preview_tmp)
        # Stem should be preserved
        assert panel._original_stem == original_stem

    def test_collect_config_interface(self, qapp):
        """Test the ConfigCollector interface."""
        panel = ConcretePanel()
        config = panel.collect_config()
        assert config == {"test": "config"}
        assert panel.collect_config_calls == 1

    def test_buttons_enabled_when_file_set(self, qapp, temp_pdf):
        """Test that buttons are enabled when a file is set."""
        panel = ConcretePanel()
        assert not panel._apply_btn.isEnabled()
        assert not panel._preview_btn.isEnabled()

        panel.set_current_file(temp_pdf)
        assert panel._apply_btn.isEnabled()
        assert panel._preview_btn.isEnabled()

    def test_buttons_disabled_when_file_cleared(self, qapp, temp_pdf):
        """Test that buttons are disabled when file is cleared."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)
        assert panel._apply_btn.isEnabled()

        panel.set_current_file(None)
        assert not panel._apply_btn.isEnabled()
        assert not panel._preview_btn.isEnabled()

    def test_reset_cancels_preview_render(self, qapp, temp_pdf):
        """Test that reset cancels any ongoing preview render."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)

        # Reset should cancel any preview rendering
        panel.reset()

        # Preview renderer should be cancelled
        assert not panel._preview_renderer.is_rendering()

    def test_preview_button_click(self, qapp, temp_pdf):
        """Test clicking preview button."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)

        # Mock the preview renderer
        panel._preview_renderer.render_preview = MagicMock(return_value=Path("temp.pdf"))

        panel._on_preview()

        # render_preview should have been called
        panel._preview_renderer.render_preview.assert_called_once()

    def test_apply_button_with_no_file(self, qapp):
        """Test applying when no file is set."""
        panel = ConcretePanel()
        # This should return early and not crash
        panel._on_apply()

    def test_file_monitor_signal_connection(self, qapp, temp_pdf):
        """Test that file monitor signal is connected."""
        panel = ConcretePanel()
        on_file_changed_spy = MagicMock()
        panel._on_file_changed = on_file_changed_spy

        # Simulate file change signal
        panel._on_file_monitored_changed(temp_pdf)

        on_file_changed_spy.assert_called_once_with(temp_pdf)

    def test_preview_ready_signal(self, qapp):
        """Test preview_ready signal emission."""
        panel = ConcretePanel()
        signal_spy = MagicMock()
        panel.preview_requested.connect(signal_spy)

        preview_path = Path("preview.pdf")
        panel._on_preview_ready(preview_path)

        signal_spy.assert_called_once_with(preview_path)

    def test_preview_failed_signal(self, qapp):
        """Test preview_failed signal handling."""
        panel = ConcretePanel()
        status_spy = MagicMock()
        panel.status_message.connect(status_spy)

        error_msg = "Preview failed"
        panel._on_preview_failed(error_msg)

        status_spy.assert_called_once_with(error_msg)

    def test_supports_preview_flag(self, qapp, temp_pdf):
        """Test _supports_preview flag disables preview button."""
        panel = ConcretePanel()
        panel._supports_preview = False
        panel.set_current_file(temp_pdf)

        assert panel._apply_btn.isEnabled()
        assert not panel._preview_btn.isEnabled()

    def test_set_busy_state(self, qapp, temp_pdf):
        """Test _set_busy method."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)

        assert panel._apply_btn.isEnabled()
        panel._set_busy(True)
        assert not panel._apply_btn.isEnabled()

        panel._set_busy(False)
        assert panel._apply_btn.isEnabled()

    def test_status_label_during_busy(self, qapp, temp_pdf):
        """Test status label updates during busy state."""
        panel = ConcretePanel()
        panel.show()
        panel.set_current_file(temp_pdf)

        assert not panel._status_label.isVisible()
        panel._set_busy(True, label="Test message")
        assert panel._status_label.isVisible()
        assert panel._status_label.text() == "Test message"

        panel._set_busy(False)
        assert not panel._status_label.isVisible()

    def test_ask_save_path_dialog(self, qapp, temp_pdf):
        """Test _ask_save_path dialog."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)

        # Mock the file dialog
        with patch("ui.panels.base_panel.QFileDialog.getSaveFileName") as mock_dialog:
            mock_dialog.return_value = ("/path/to/output.pdf", "")
            result = panel._ask_save_path()

            assert result == Path("/path/to/output.pdf")

    def test_ask_save_path_adds_pdf_extension(self, qapp, temp_pdf):
        """Test that _ask_save_path adds .pdf extension if missing."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)

        with patch("ui.panels.base_panel.QFileDialog.getSaveFileName") as mock_dialog:
            mock_dialog.return_value = ("/path/to/output", "")
            result = panel._ask_save_path()

            assert result.suffix == ".pdf"

    def test_ask_save_path_cancelled(self, qapp, temp_pdf):
        """Test _ask_save_path when user cancels."""
        panel = ConcretePanel()
        panel.set_current_file(temp_pdf)

        with patch("ui.panels.base_panel.QFileDialog.getSaveFileName") as mock_dialog:
            mock_dialog.return_value = ("", "")
            result = panel._ask_save_path()

            assert result is None

    def test_error_handler(self, qapp):
        """Test error handler.

        ``_on_error`` mostra un QMessageBox.critical() modale che bloccherebbe
        il test (specie con la piattaforma 'offscreen' su CI), quindi va
        mockato: qui verifichiamo solo la logica di stato e il segnale.
        """
        panel = ConcretePanel()
        status_spy = MagicMock()
        panel.status_message.connect(status_spy)

        error_msg = "Test error"
        with patch("ui.panels.base_panel.QMessageBox.critical") as mock_critical:
            panel._on_error(error_msg)
            mock_critical.assert_called_once()

        # Should update status and disable busy state
        assert panel._apply_btn.isEnabled()
        status_spy.assert_called_once()


class TestBasePanelWidgetIntegration:
    """Integration tests for BasePanelWidget with components."""

    def test_file_monitor_integration(self, qapp, temp_pdf):
        """Test FileMonitorManager integration."""
        panel = ConcretePanel()
        file_changed_spy = MagicMock()
        panel._on_file_changed = file_changed_spy

        # FileMonitor should be available
        assert panel._file_monitor is not None
        panel._file_monitor.watch_file(temp_pdf)
        assert temp_pdf in panel._file_monitor._watched_paths

    def test_preview_renderer_integration(self, qapp, temp_pdf):
        """Test PreviewRenderer integration."""
        panel = ConcretePanel()
        assert panel._preview_renderer is not None
        assert not panel._preview_renderer.is_rendering()

    def test_config_collector_integration(self, qapp):
        """Test ConfigCollector integration."""
        panel = ConcretePanel()
        # BasePanelWidget should implement ConfigCollector
        from ui.panels.config_collector import ConfigCollector
        assert isinstance(panel, ConfigCollector)

        config = panel.collect_config()
        assert config == {"test": "config"}
