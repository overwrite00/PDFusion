"""Regressione: l'anteprima Intestazioni/Piè di pagina non deve diventare la nuova sorgente.

``HeadersFootersPanel`` deve ricordare il file di anteprima che produce (``_hf_last_output``)
per ignorarlo quando ``MainWindow`` lo propaga ai pannelli con ``set_current_file()``:
altrimenti l'anteprima successiva (o "Applica") parte dal file che ha GIÀ le intestazioni
e le sovrappone. L'override però si chiamava ``_on_preview_done``, un gancio che non esiste
(quello vero della base, collegato al segnale del renderer, è ``_on_preview_ready``), quindi
non veniva mai chiamato e ``_hf_last_output`` restava ``None``. ``mypy`` lo segnalava
(``"_on_preview_done" undefined in superclass``).
"""

import shutil

import pytest

from ui.panels.headers_footers_panel import HeadersFootersPanel


@pytest.fixture
def panel(qtbot):
    p = HeadersFootersPanel()
    qtbot.addWidget(p)
    return p


@pytest.fixture
def preview_file(tmp_path, sample_pdf):
    tmp = tmp_path / "preview_tmp.pdf"
    shutil.copy(sample_pdf, tmp)
    return tmp


def test_preview_output_is_not_taken_as_the_new_base(panel, sample_pdf, preview_file):
    panel.set_current_file(sample_pdf)
    assert panel._hf_base_path == sample_pdf

    panel._on_preview_ready(preview_file)  # la preview è pronta (segnale del renderer)
    panel.set_current_file(preview_file)  # MainWindow la propaga a tutti i pannelli

    assert panel._hf_last_output == preview_file
    assert panel._hf_base_path == sample_pdf  # la sorgente resta il documento pulito


def test_preview_still_reaches_the_main_window(qtbot, panel, sample_pdf, preview_file):
    panel.set_current_file(sample_pdf)
    with qtbot.waitSignal(panel.preview_requested, timeout=1000) as blocker:
        panel._on_preview_ready(preview_file)
    assert blocker.args == [preview_file]


def test_opening_another_document_updates_the_base(panel, sample_pdf, multipage_pdf, preview_file):
    panel.set_current_file(sample_pdf)
    panel._on_preview_ready(preview_file)
    panel.set_current_file(multipage_pdf)  # un documento vero, non la nostra anteprima
    assert panel._hf_base_path == multipage_pdf


def test_empty_preview_file_is_not_remembered(panel, sample_pdf, tmp_path):
    empty = tmp_path / "empty_preview.pdf"
    empty.write_bytes(b"")
    panel.set_current_file(sample_pdf)
    panel._on_preview_ready(empty)
    assert panel._hf_last_output is None  # file vuoto/non valido: non lo si registra
