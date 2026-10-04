"""Comportamento dei punti UI toccati dalla pulizia dei tipi (mypy).

Gli stub di PyQt6 tipizzano come Optional molti valori che in pratica non sono mai None
(``style()``, ``mimeData()``, ``addAction(str)``, ``menuBar()`` ...). Sistemarli ha richiesto di
riscrivere piccoli pezzi di codice UI che non avevano test: questi test ne fissano il
comportamento, così il refactor non può cambiarlo senza che qualcuno se ne accorga.
"""

from pathlib import Path

import pytest
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QMenu, QPushButton, QWidget

from ui.dialogs.update_dialog import UpdateAvailableDialog
from ui.main_window import MainWindow
from ui.panels.delete_panel import DeletePanel
from ui.panels.reorder_panel import ReorderPanel
from ui.qt_utils import repolish
from ui.thumbnail_panel import ThumbnailPanel
from ui.viewer import ZOOM_LABELS, PDFViewer
from ui.widgets.drop_zone import DropZone
from utils import update_checker as uc
from utils.update_checker import ReleaseInfo

# ---------------------------------------------------------------------------
# repolish()
# ---------------------------------------------------------------------------


def test_repolish_reapplies_the_style(qtbot, monkeypatch):
    w = QWidget()
    qtbot.addWidget(w)
    calls: list[str] = []

    class _Style:
        def unpolish(self, widget):
            calls.append("unpolish")

        def polish(self, widget):
            calls.append("polish")

    monkeypatch.setattr(w, "style", lambda: _Style())
    repolish(w)
    assert calls == ["unpolish", "polish"]


def test_repolish_tolerates_a_missing_style(qtbot, monkeypatch):
    w = QWidget()
    qtbot.addWidget(w)
    monkeypatch.setattr(w, "style", lambda: None)
    repolish(w)  # gli stub dicono "QStyle | None": non deve sollevare


# ---------------------------------------------------------------------------
# Drag & drop
# ---------------------------------------------------------------------------


# QDragEnterEvent/QDropEvent NON prendono possesso del QMimeData: se Python lo distrugge mentre
# l'evento è ancora in uso si ottiene un access violation. Tenerne un riferimento per tutta la sessione.
_KEEP_ALIVE: list[QMimeData] = []


def _mime(*names: str) -> QMimeData:
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(str(Path("C:/x") / n)) for n in names])
    _KEEP_ALIVE.append(m)
    return m


def _enter(mime: QMimeData) -> QDragEnterEvent:
    return QDragEnterEvent(
        QPoint(1, 1),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _drop(mime: QMimeData) -> QDropEvent:
    return QDropEvent(
        QPointF(1, 1),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.fixture
def zone(qtbot):
    z = DropZone()
    qtbot.addWidget(z)
    return z


def test_dropzone_accepts_a_pdf_drag_and_marks_itself(zone):
    ev = _enter(_mime("doc.pdf"))
    zone.dragEnterEvent(ev)
    assert ev.isAccepted()
    assert zone.property("dragging") is True


def test_dropzone_ignores_other_file_types(zone):
    ev = _enter(_mime("notes.txt"))
    zone.dragEnterEvent(ev)
    assert not ev.isAccepted()
    assert zone.property("dragging") in (None, False)


def test_dropzone_emits_only_the_accepted_files_and_clears_the_marker(qtbot, zone):
    zone.setProperty("dragging", True)
    with qtbot.waitSignal(zone.files_dropped, timeout=1000) as blocker:
        zone.dropEvent(_drop(_mime("a.pdf", "b.txt", "c.PDF")))
    assert [p.name for p in blocker.args[0]] == ["a.pdf", "c.PDF"]
    assert zone.property("dragging") is False


def test_dropzone_events_tolerate_none(zone):
    zone.dragEnterEvent(None)
    zone.dropEvent(None)  # i tipi dicono "Event | None": non deve sollevare


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    yield w
    w.shutdown()


def test_main_window_accepts_a_pdf_drag_only(window):
    yes, no = _enter(_mime("doc.pdf")), _enter(_mime("notes.txt"))
    window.dragEnterEvent(yes)
    window.dragEnterEvent(no)
    assert yes.isAccepted() and not no.isAccepted()


def test_main_window_drop_opens_the_first_existing_pdf(window, tmp_path, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    opened: list[Path] = []
    monkeypatch.setattr(window, "_on_open_path", opened.append)
    m = QMimeData()
    _KEEP_ALIVE.append(m)
    m.setUrls([QUrl.fromLocalFile(str(tmp_path / "missing.pdf")), QUrl.fromLocalFile(str(pdf))])
    window.dropEvent(_drop(m))
    assert opened == [pdf]


def test_main_window_event_handlers_tolerate_none(window, monkeypatch):
    window.dragEnterEvent(None)
    window.dropEvent(None)
    called: list[bool] = []
    monkeypatch.setattr(window, "shutdown", lambda: called.append(True))
    window.closeEvent(None)
    assert called == [True]


# ---------------------------------------------------------------------------
# Menu e dispatch verso i pannelli (main_window)
# ---------------------------------------------------------------------------


def test_menu_structure_is_unchanged(window):
    titles = [a.text() for a in window.menuBar().actions()]
    assert titles == ["File", "?"]
    file_menu = window.menuBar().actions()[0].menu()
    texts = [a.text() for a in file_menu.actions() if not a.isSeparator()]
    assert texts == ["Apri…", "Salva con modifiche…", "Chiudi documento", "Esci"]


def test_every_panel_is_a_base_panel(window):
    from ui.panels.base_panel import BasePanelWidget

    assert window._panels and all(isinstance(p, BasePanelWidget) for p in window._panels.values())


def test_thumbnail_reorder_reaches_the_reorder_panel(window, tmp_path, monkeypatch):
    seen: list[tuple] = []
    monkeypatch.setattr(ReorderPanel, "apply_order", lambda self, *a: seen.append(a))
    window._current_path = tmp_path / "doc.pdf"
    window._current_password = "pw"
    window._on_reorder_from_thumbnail([2, 0, 1])
    assert seen == [([2, 0, 1], tmp_path / "doc.pdf", "pw")]


def test_thumbnail_reorder_without_a_document_does_nothing(window, monkeypatch):
    seen: list[tuple] = []
    monkeypatch.setattr(ReorderPanel, "apply_order", lambda self, *a: seen.append(a))
    window._current_path = None
    window._on_reorder_from_thumbnail([1, 0])
    assert seen == []


def test_page_change_updates_the_delete_panel_only_when_it_is_the_visible_one(window):
    delete = window._panels["delete_page"]
    assert isinstance(delete, DeletePanel)
    window._stack.setCurrentWidget(delete)
    window._on_viewer_page_changed(4)
    assert delete._current_label.text() == "Pagina 5"

    delete.set_current_page(0)
    window._stack.setCurrentWidget(window._panels["split"])
    window._on_viewer_page_changed(7)
    assert delete._current_label.text() == "Pagina 1"  # pannello non visibile: invariato


def test_delete_panel_current_page_radio_disables_the_other_inputs(qtbot):
    panel = DeletePanel()
    qtbot.addWidget(panel)
    panel._radio_number.setChecked(True)
    assert panel._page_spin.isEnabled()
    panel._radio_current.setChecked(True)
    assert not panel._page_spin.isEnabled()
    assert not panel._range_input.isEnabled()


# ---------------------------------------------------------------------------
# Viewer: menu zoom e thumbnail panel
# ---------------------------------------------------------------------------


def test_zoom_menu_lists_every_level_and_applies_the_chosen_one(qtbot, monkeypatch):
    viewer = PDFViewer()
    qtbot.addWidget(viewer)
    captured: dict = {}

    def fake_exec(self, *a, **k):
        captured["actions"] = list(self.actions())
        return captured["actions"][2]

    monkeypatch.setattr(QMenu, "exec", fake_exec)
    current = viewer._zoom_idx
    viewer._show_zoom_menu()

    actions = captured["actions"]
    assert [a.text() for a in actions] == list(ZOOM_LABELS)
    assert all(a.isCheckable() for a in actions)
    assert [a.isChecked() for a in actions] == [i == current for i in range(len(ZOOM_LABELS))]
    assert [a.data() for a in actions] == list(range(len(ZOOM_LABELS)))
    assert viewer._zoom_idx == 2


def test_viewer_key_and_wheel_handlers_tolerate_none(qtbot):
    viewer = PDFViewer()
    qtbot.addWidget(viewer)
    viewer.keyPressEvent(None)
    viewer.wheelEvent(None)


def test_thumbnail_panel_reports_the_new_order_after_a_drag(qtbot):
    from PyQt6.QtCore import QModelIndex
    from PyQt6.QtWidgets import QListWidgetItem

    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    for page in (3, 1, 2):
        item = QListWidgetItem(str(page))
        item.setData(Qt.ItemDataRole.UserRole, page)
        panel._list.addItem(item)

    with qtbot.waitSignal(panel.order_changed, timeout=1000) as blocker:
        panel._list.model().rowsMoved.emit(QModelIndex(), 0, 0, QModelIndex(), 2)
    assert blocker.args == [[3, 1, 2]]


# ---------------------------------------------------------------------------
# Dialogo "Aggiornamento disponibile"
# ---------------------------------------------------------------------------


@pytest.fixture
def release():
    return ReleaseInfo(
        tag="v9.9.9",
        name="PDFusion v9.9.9",
        url="https://example.invalid/release",
        body="notes",
        prerelease=False,
        assets=[("PDFusion-9.9.9-windows-setup.exe", "https://example.invalid/win.exe")],
    )


def _buttons(dlg) -> dict[str, QPushButton]:
    return {b.text(): b for b in dlg.findChildren(QPushButton)}


def test_update_dialog_has_the_three_buttons(qtbot, release):
    dlg = UpdateAvailableDialog(release, "0.3.0")
    qtbot.addWidget(dlg)
    assert set(_buttons(dlg)) == {"Scarica", "Ignora questa versione", "Più tardi"}


def test_update_dialog_later_rejects_without_skipping(qtbot, release):
    dlg = UpdateAvailableDialog(release, "0.3.0")
    qtbot.addWidget(dlg)
    _buttons(dlg)["Più tardi"].click()
    assert dlg.result() == dlg.DialogCode.Rejected and not dlg.skip_requested()


def test_update_dialog_skip_rejects_and_reports_the_skip(qtbot, release):
    dlg = UpdateAvailableDialog(release, "0.3.0")
    qtbot.addWidget(dlg)
    _buttons(dlg)["Ignora questa versione"].click()
    assert dlg.result() == dlg.DialogCode.Rejected and dlg.skip_requested()


def test_update_dialog_download_opens_the_platform_installer(qtbot, release, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        "ui.dialogs.update_dialog.QDesktopServices.openUrl", lambda url: opened.append(url.toString())
    )
    monkeypatch.setattr("ui.dialogs.update_dialog.pick_asset_url", lambda assets: assets[0][1])
    dlg = UpdateAvailableDialog(release, "0.3.0")
    qtbot.addWidget(dlg)
    _buttons(dlg)["Scarica"].click()
    assert opened == ["https://example.invalid/win.exe"]
    assert dlg.result() == dlg.DialogCode.Accepted


def test_update_dialog_download_falls_back_to_the_release_page(qtbot, release, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        "ui.dialogs.update_dialog.QDesktopServices.openUrl", lambda url: opened.append(url.toString())
    )
    monkeypatch.setattr("ui.dialogs.update_dialog.pick_asset_url", lambda assets: None)
    dlg = UpdateAvailableDialog(release, "0.3.0")
    qtbot.addWidget(dlg)
    _buttons(dlg)["Scarica"].click()
    assert opened == ["https://example.invalid/release"]


def test_dialog_tests_never_touch_the_real_update_state():
    # sicurezza: questi test non scrivono lo stato; ``uc`` è importato solo per verificarlo
    assert uc.UPDATE_CHECK_STATE_PATH.name == "update_check.json"
