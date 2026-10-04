"""Regressione: il pulsante "Applica" dei pannelli Dividi, Esporta immagini e Batch.

Questi tre pannelli sovrascrivono ``_on_apply()`` e chiamavano ``self._collect_config()``,
un nome che non esiste: il mixin ``ConfigCollector`` espone ``collect_config()`` (senza
underscore). Premere "Applica" sollevava ``AttributeError`` e lo strumento non faceva nulla.
Residuo del refactor che ha estratto ``ConfigCollector`` da ``BasePanelWidget``; ``mypy``
lo segnalava (``"SplitPanel" has no attribute "_collect_config"``) ma non c'erano test che
arrivassero fino a lì.

I test percorrono il flusso reale: scelta della cartella (dialog finto), worker su QThread
reale e core reale; si attende il segnale di fine e si controllano i file prodotti.
"""

import pytest
from PyQt6.QtWidgets import QFileDialog

from ui.panels.batch_panel import BatchPanel
from ui.panels.export_images_panel import ExportImagesPanel
from ui.panels.split_panel import SplitPanel

_TIMEOUT_MS = 20_000


@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(out))
    )
    return out


def _join_thread(panel) -> None:
    """Attende la fine del QThread del pannello, così il teardown non lo trova attivo."""
    thread = getattr(panel, "_thread", None)
    if thread is not None:
        thread.quit()
        thread.wait(5000)


def test_split_apply_runs_and_writes_parts(qtbot, multipage_pdf, output_dir):
    panel = SplitPanel()
    qtbot.addWidget(panel)
    panel.set_current_file(multipage_pdf)
    panel._n_spin.setValue(3)

    with qtbot.waitSignal(panel.operation_done, timeout=_TIMEOUT_MS):
        panel._on_apply()
    _join_thread(panel)

    parts = sorted(output_dir.glob("*.pdf"))
    assert len(parts) >= 2, parts


def test_split_apply_does_nothing_when_the_range_is_invalid(qtbot, multipage_pdf, output_dir):
    panel = SplitPanel()
    qtbot.addWidget(panel)
    panel.set_current_file(multipage_pdf)
    panel._radio_range.setChecked(True)
    panel._range_input.set_text("abc")  # non valido: collect_config() ritorna None
    assert not panel._range_input.is_valid()

    panel._on_apply()  # non deve sollevare né avviare nulla

    assert list(output_dir.iterdir()) == []
    assert getattr(panel, "_thread", None) is None


def test_export_images_apply_runs_and_writes_images(qtbot, sample_pdf, output_dir):
    panel = ExportImagesPanel()
    qtbot.addWidget(panel)
    panel.set_current_file(sample_pdf)

    with qtbot.waitSignal(panel.operation_done, timeout=_TIMEOUT_MS):
        panel._on_apply()
    _join_thread(panel)

    assert any(p.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff")
               for p in output_dir.iterdir())


def test_batch_apply_runs_and_reports_completion(qtbot, sample_pdf, output_dir):
    panel = BatchPanel()
    qtbot.addWidget(panel)
    panel._files.append(sample_pdf)

    with qtbot.waitSignal(
        panel.status_message,
        timeout=_TIMEOUT_MS,
        check_params_cb=lambda msg: msg.startswith("Batch completato"),
    ):
        panel._on_apply()
    _join_thread(panel)

    assert any(output_dir.glob("*.pdf"))


def test_batch_apply_without_files_returns_quietly(qtbot, output_dir):
    panel = BatchPanel()
    qtbot.addWidget(panel)

    panel._on_apply()  # nessun file: collect_config() avvisa e ritorna None

    assert list(output_dir.iterdir()) == []
