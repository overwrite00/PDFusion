"""Tests for FileMonitorManager."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QCoreApplication

from ui.panels.file_monitor import FileMonitorManager


@pytest.fixture
def qapp():
    """Provide QApplication for Qt tests."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    yield app


@pytest.fixture
def temp_pdf(tmp_path):
    """Create a temporary PDF file."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("dummy pdf content")
    return pdf_path


class TestFileMonitorManager:
    """Test FileMonitorManager functionality."""

    def test_initialization(self, qapp):
        """Test FileMonitorManager initializes correctly."""
        monitor = FileMonitorManager()
        assert monitor is not None
        assert not monitor._watched_paths

    def test_watch_file(self, qapp, temp_pdf):
        """Test watching a file."""
        monitor = FileMonitorManager()
        monitor.watch_file(temp_pdf)
        assert temp_pdf in monitor._watched_paths

    def test_watch_nonexistent_file(self, qapp, tmp_path):
        """Test watching a nonexistent file does nothing."""
        monitor = FileMonitorManager()
        nonexistent = tmp_path / "nonexistent.pdf"
        monitor.watch_file(nonexistent)
        assert nonexistent not in monitor._watched_paths

    def test_watch_none_path(self, qapp):
        """Test watching None path does nothing."""
        monitor = FileMonitorManager()
        monitor.watch_file(None)
        assert len(monitor._watched_paths) == 0

    def test_unwatch_file(self, qapp, temp_pdf):
        """Test unwatching a file."""
        monitor = FileMonitorManager()
        monitor.watch_file(temp_pdf)
        assert temp_pdf in monitor._watched_paths
        monitor.unwatch_file(temp_pdf)
        assert temp_pdf not in monitor._watched_paths

    def test_unwatch_nonexistent_file(self, qapp, tmp_path):
        """Test unwatching a nonexistent file does nothing."""
        monitor = FileMonitorManager()
        nonexistent = tmp_path / "nonexistent.pdf"
        monitor.unwatch_file(nonexistent)  # Should not raise

    def test_clear_watches(self, qapp, tmp_path):
        """Test clearing all watches."""
        monitor = FileMonitorManager()
        pdf1 = tmp_path / "test1.pdf"
        pdf2 = tmp_path / "test2.pdf"
        pdf1.write_text("content1")
        pdf2.write_text("content2")

        monitor.watch_file(pdf1)
        monitor.watch_file(pdf2)
        assert len(monitor._watched_paths) == 2

        monitor.clear_watches()
        assert len(monitor._watched_paths) == 0

    def test_file_changed_signal(self, qapp, temp_pdf):
        """Test file_changed signal is emitted."""
        monitor = FileMonitorManager()
        signal_spy = MagicMock()
        monitor.file_changed.connect(signal_spy)

        monitor.watch_file(temp_pdf)
        # Simulate file change
        monitor._on_file_changed(str(temp_pdf))

        signal_spy.assert_called_once()
        # Signal should emit the Path
        assert signal_spy.call_args[0][0] == temp_pdf

    def test_file_changed_with_invalid_path(self, qapp):
        """Test file_changed with invalid path string."""
        monitor = FileMonitorManager()
        signal_spy = MagicMock()
        monitor.file_changed.connect(signal_spy)

        # This should not raise
        monitor._on_file_changed("invalid::path")
        # Signal may or may not be called depending on error handling

    def test_multiple_watches(self, qapp, tmp_path):
        """Test monitoring multiple files."""
        monitor = FileMonitorManager()
        files = [tmp_path / f"test{i}.pdf" for i in range(3)]
        for i, f in enumerate(files):
            f.write_text(f"content{i}")

        for f in files:
            monitor.watch_file(f)

        assert len(monitor._watched_paths) == 3
        for f in files:
            assert f in monitor._watched_paths
