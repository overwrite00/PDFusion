import pytest
import pikepdf
from core.rotate import rotate_pages, rotate_all
from utils.exceptions import PDFusionError


class TestRotatePages:
    def test_rotate_one_page_90(self, sample_pdf, tmp_output):
        result = rotate_pages(sample_pdf, [0], 90, tmp_output)
        with pikepdf.open(result) as pdf:
            assert int(pdf.pages[0].get("/Rotate", 0)) == 90

    def test_rotate_180(self, sample_pdf, tmp_output):
        result = rotate_pages(sample_pdf, [0], 180, tmp_output)
        with pikepdf.open(result) as pdf:
            assert int(pdf.pages[0].get("/Rotate", 0)) == 180

    def test_rotate_multiple_pages(self, multipage_pdf, tmp_output):
        result = rotate_pages(multipage_pdf, [0, 2, 4], 270, tmp_output)
        with pikepdf.open(result) as pdf:
            assert int(pdf.pages[0].get("/Rotate", 0)) == 270
            assert int(pdf.pages[2].get("/Rotate", 0)) == 270
            assert int(pdf.pages[4].get("/Rotate", 0)) == 270
            # Pagine non rotate rimangono invariate
            assert int(pdf.pages[1].get("/Rotate", 0)) == 0

    def test_rotate_all_pages(self, multipage_pdf, tmp_output):
        result = rotate_all(multipage_pdf, 90, tmp_output)
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                assert int(page.get("/Rotate", 0)) == 90

    def test_invalid_degrees_raises(self, sample_pdf, tmp_output):
        with pytest.raises(PDFusionError):
            rotate_pages(sample_pdf, [0], 45, tmp_output)

    def test_empty_indices_rotates_all(self, multipage_pdf, tmp_output):
        result = rotate_pages(multipage_pdf, [], 90, tmp_output)
        with pikepdf.open(result) as pdf:
            assert int(pdf.pages[0].get("/Rotate", 0)) == 90
