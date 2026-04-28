import pikepdf
import pytest

from core.delete_page import delete_pages
from utils.exceptions import InvalidPageRangeError


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
        with pytest.raises(ValueError):
            delete_pages(sample_pdf, [0], tmp_output)

    def test_delete_out_of_bounds_raises(self, multipage_pdf, tmp_output):
        with pytest.raises(InvalidPageRangeError):
            delete_pages(multipage_pdf, [99], tmp_output)

    def test_inplace_overwrite(self, multipage_pdf, tmp_output):
        import shutil
        shutil.copy(multipage_pdf, tmp_output)
        result = delete_pages(tmp_output, [0], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 9
