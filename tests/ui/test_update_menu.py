"""Test della voce di menu "Controlla aggiornamenti all'avvio" e del suo effetto.

Nessuna rete e nessuna scrittura in ~/.pdfusion: lo stato è reindirizzato su tmp_path
PRIMA di creare la MainWindow (la finestra legge lo stato in costruzione e il toggle lo
scrive), e ``_check_for_updates`` è sempre sostituita da un registratore.
"""

import pytest
from PyQt6.QtGui import QAction

from ui.main_window import MainWindow
from utils import update_checker as uc

_TEXT = "Controlla aggiornamenti all'avvio"


@pytest.fixture
def state_file(monkeypatch, tmp_path):
    path = tmp_path / "pdfusion" / "update_check.json"
    monkeypatch.setattr(uc, "UPDATE_CHECK_STATE_PATH", path)
    return path


def _make_window(qtbot) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    return window


@pytest.fixture
def window(qtbot, state_file):
    w = _make_window(qtbot)
    yield w
    try:
        w.shutdown()
    except Exception:
        pass


def _help_action(window: MainWindow, text: str) -> QAction:
    help_menu = next(a.menu() for a in window.menuBar().actions() if a.text() == "?")
    return next(a for a in help_menu.actions() if a.text() == text)


def test_menu_item_exists_checkable_and_checked_by_default(window):
    act = _help_action(window, _TEXT)
    assert act.isCheckable() is True
    assert act.isChecked() is True


def test_building_the_window_does_not_write_state(window, state_file):
    # il valore iniziale viene impostato prima di collegare toggled
    assert not state_file.exists()


def test_unchecking_disables_auto_check_and_persists(window, state_file):
    act = _help_action(window, _TEXT)
    act.trigger()  # checkable: inverte lo stato ed emette toggled
    assert act.isChecked() is False
    assert uc.is_auto_check_enabled() is False
    assert uc.should_auto_check() is False
    act.trigger()
    assert act.isChecked() is True
    assert uc.is_auto_check_enabled() is True


def test_choice_is_restored_by_a_new_window(qtbot, state_file):
    first = _make_window(qtbot)
    _help_action(first, _TEXT).trigger()
    first.shutdown()
    second = _make_window(qtbot)
    try:
        assert _help_action(second, _TEXT).isChecked() is False
    finally:
        second.shutdown()


def test_manual_check_entry_is_still_present(window):
    assert _help_action(window, "Controlla aggiornamenti…") is not None


def _record_checks(window, monkeypatch) -> list[bool]:
    calls: list[bool] = []
    monkeypatch.setattr(window, "_check_for_updates", lambda manual: calls.append(manual))
    return calls


def test_pytest_guard_still_blocks_the_automatic_check(window, monkeypatch):
    """La guardia PYTEST_CURRENT_TEST è essenziale: senza, ogni MainWindow() nei test
    avvierebbe una vera chiamata di rete su un QThread (vedi CLAUDE.md)."""
    calls = _record_checks(window, monkeypatch)
    window._maybe_auto_check_updates()  # PYTEST_CURRENT_TEST è impostata da pytest
    assert calls == []


def test_automatic_check_runs_when_enabled_and_not_under_pytest(window, monkeypatch):
    calls = _record_checks(window, monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    window._maybe_auto_check_updates()
    assert calls == [False]  # manual=False: controllo silenzioso


def test_automatic_check_is_skipped_when_disabled(window, monkeypatch):
    calls = _record_checks(window, monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    _help_action(window, _TEXT).trigger()  # disattiva
    window._maybe_auto_check_updates()
    assert calls == []
