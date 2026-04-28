import pikepdf
import pytest

from core.reorder import reorder_pages
from utils.exceptions import PDFusionError


class TestReorderPages:
    def test_reverse_all(self, multipage_pdf, tmp_output):
        new_order = list(range(9, -1, -1))
        result = reorder_pages(multipage_pdf, new_order, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_identity(self, multipage_pdf, tmp_output):
        new_order = list(range(10))
        result = reorder_pages(multipage_pdf, new_order, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_swap_first_last(self, multipage_pdf, tmp_output):
        order = list(range(10))
        order[0], order[-1] = order[-1], order[0]
        result = reorder_pages(multipage_pdf, order, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_wrong_length_raises(self, multipage_pdf, tmp_output):
        with pytest.raises(PDFusionError):
            reorder_pages(multipage_pdf, [0, 1], tmp_output)

    def test_duplicate_index_raises(self, multipage_pdf, tmp_output):
        # Due indici uguali → non è una permutazione valida
        order = [0, 0, 2, 3, 4, 5, 6, 7, 8, 9]
        with pytest.raises(PDFusionError):
            reorder_pages(multipage_pdf, order, tmp_output)

    def test_out_of_range_raises(self, multipage_pdf, tmp_output):
        order = list(range(9)) + [99]
        with pytest.raises(PDFusionError):
            reorder_pages(multipage_pdf, order, tmp_output)
