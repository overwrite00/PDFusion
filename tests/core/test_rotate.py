import logging

import pikepdf
import pytest

from core.rotate import rotate_all, rotate_pages
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

    def test_out_of_bounds_index_raises(self, sample_pdf, tmp_output):
        """Rotating out-of-bounds page should raise PDFusionError."""
        with pytest.raises(PDFusionError, match="non esiste"):
            rotate_pages(sample_pdf, [999], 90, tmp_output)

    def test_negative_out_of_bounds_raises(self, sample_pdf, tmp_output):
        """Rotating with invalid negative index should raise."""
        with pytest.raises(PDFusionError):
            rotate_pages(sample_pdf, [-999], 90, tmp_output)

    def test_rotation_logs_operation(self, multipage_pdf, tmp_output, caplog):
        """Rotation should log the operation."""
        with caplog.at_level(logging.INFO):
            rotate_pages(multipage_pdf, [0, 1, 2], 90, tmp_output)

        assert "rotate" in caplog.text.lower()
        assert "90" in caplog.text
