"""File monitoring functionality for PDF panels.

Responsibility: Watch for file changes via QFileSystemWatcher and emit signals.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, pyqtSignal

logger = logging.getLogger(__name__)


class FileMonitorManager(QObject):
    """Monitors file changes and emits signals when files are modified.

    Responsibility: ONLY file change detection via QFileSystemWatcher.

    Signals:
        file_changed(Path): Emitted when a monitored file changes.
    """

    file_changed = pyqtSignal(Path)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._watched_paths: set[Path] = set()

    def watch_file(self, path: Path) -> None:
        """Start watching a file for changes.

        Args:
            path: The file path to watch. Must exist.
        """
        if path is None or not path.exists():
            return

        path_str = str(path)
        if path_str not in self._watcher.files():
            try:
                self._watcher.addPath(path_str)
                self._watched_paths.add(path)
                logger.debug(f"FileMonitor: watching {path}")
            except Exception as e:
                logger.warning(f"FileMonitor: failed to watch {path}: {e}")

    def unwatch_file(self, path: Path) -> None:
        """Stop watching a file.

        Args:
            path: The file path to stop watching.
        """
        if path is None:
            return

        path_str = str(path)
        if path_str in self._watcher.files():
            try:
                self._watcher.removePath(path_str)
                self._watched_paths.discard(path)
                logger.debug(f"FileMonitor: stopped watching {path}")
            except Exception as e:
                logger.warning(f"FileMonitor: failed to unwatch {path}: {e}")

    def clear_watches(self) -> None:
        """Stop watching all files."""
        for path in list(self._watched_paths):
            self.unwatch_file(path)

    def _on_file_changed(self, path_str: str) -> None:
        """Internal slot called when a watched file changes.

        Args:
            path_str: The file path (str) that changed.
        """
        try:
            path = Path(path_str)
            logger.debug(f"FileMonitor: file changed - {path}")
            self.file_changed.emit(path)
        except Exception as e:
            logger.error(f"FileMonitor: error processing file change: {e}")
