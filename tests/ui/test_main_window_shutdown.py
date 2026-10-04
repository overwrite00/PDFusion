"""``MainWindow.shutdown()``: tutti i passi di cleanup, ed è idempotente.

``shutdown()`` non aveva test. Il primo passo fa ``self.destroyed.disconnect()``, che in
PyQt6 solleva ``TypeError`` (non ``RuntimeError``) se il segnale non ha connessioni: alla
SECONDA chiamata sulla stessa finestra l'eccezione finiva nell'``except Exception`` esterno,
che registrava un errore e usciva saltando i passi successivi. La prima chiamata (compresa
la vera chiusura via ``closeEvent``) funzionava; la seconda succede nei test (fixture +
chiusura di qtbot) e riempiva i log di errori che nascondevano quelli veri.
"""

import logging
from pathlib import Path

import pytest

from ui.main_window import MainWindow


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    return w


def _errors(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


def test_shutdown_does_not_log_an_error(window, caplog):
    with caplog.at_level(logging.ERROR, logger="ui.main_window"):
        window.shutdown()
    assert _errors(caplog) == []


def test_shutdown_runs_every_step_in_order(window, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(window._viewer, "close_document", lambda: calls.append("viewer"))
    monkeypatch.setattr(window._thumbnails, "close_document", lambda: calls.append("thumbs"))
    monkeypatch.setattr(window, "_cleanup_all_temps", lambda: calls.append("temps"))
    window.shutdown()
    assert calls == ["viewer", "thumbs", "temps"]


def test_shutdown_closes_the_document_and_removes_session_temp_files(
    window, qtbot, sample_pdf, tmp_path
):
    window.open_file(sample_pdf)
    qtbot.wait(500)
    assert window._viewer._worker is not None  # documento caricato

    leftover = tmp_path / "preview_tmp.pdf"
    leftover.write_bytes(b"%PDF-1.4\n")
    window._temp_files.append(Path(leftover))

    window.shutdown()

    assert window._viewer._worker is None
    assert not leftover.exists()
    assert window._temp_files == []


def test_shutdown_is_idempotent(window, caplog):
    with caplog.at_level(logging.ERROR, logger="ui.main_window"):
        window.shutdown()
        window.shutdown()
    assert _errors(caplog) == []
