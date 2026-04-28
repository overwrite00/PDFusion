import shutil

import pikepdf
import pytest

from core.delete_page import delete_pages
from utils.exceptions import PDFusionError


class TestDeletePages:
    def test_delete_first(self, multipage_pdf, tmp_output):
        result = delete_pages(multipage_pdf, [0], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 9

    def test_delete_last(self, multipage_pdf, tmp_output):
        result = delete_pages(multipage_pdf, [9], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 9

    def test_delete_multiple(self, multipage_pdf, tmp_output):
        result = delete_pages(multipage_pdf, [0, 2, 4], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 7

    def test_delete_all_raises(self, sample_pdf, tmp_output):
        with pytest.raises(PDFusionError):
            delete_pages(sample_pdf, [0], tmp_output)

    def test_delete_out_of_bounds_raises(self, multipage_pdf, tmp_output):
        with pytest.raises(PDFusionError):
            delete_pages(multipage_pdf, [99], tmp_output)

    def test_inplace_overwrite(self, multipage_pdf, tmp_path):
        # Usa un percorso di output distinto dall'input per evitare lock su Windows
        src = tmp_path / "source.pdf"
        dst = tmp_path / "output.pdf"
        shutil.copy(multipage_pdf, src)
        result = delete_pages(src, [0], dst)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 9
