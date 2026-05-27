import logging

import pikepdf
import pytest

from core.extract_pages import extract_pages
from utils.exceptions import PDFusionError


class TestExtractPages:
    def test_extract_range(self, multipage_pdf, tmp_output):
        result = extract_pages(multipage_pdf, ranges=[(2, 5)], output_path=tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 4

    def test_extract_mixed(self, multipage_pdf, tmp_output):
        result = extract_pages(multipage_pdf, ranges=[(1, 2), (8, 10)], output_path=tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 5

    def test_extract_single(self, multipage_pdf, tmp_output):
        result = extract_pages(multipage_pdf, ranges=[(6, 6)], output_path=tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_extract_out_of_bounds_raises(self, multipage_pdf, tmp_output):
        """Extracting out-of-bounds page range should raise PDFusionError."""
        with pytest.raises(PDFusionError, match="supera il totale"):
            extract_pages(multipage_pdf, ranges=[(1, 999)], output_path=tmp_output)

    def test_extract_invalid_range_raises(self, multipage_pdf, tmp_output):
        """Extracting with end < start should raise."""
        with pytest.raises(PDFusionError, match="non valido"):
            extract_pages(multipage_pdf, ranges=[(5, 3)], output_path=tmp_output)

    def test_extraction_logs_operation(self, multipage_pdf, tmp_output, caplog):
        """Extraction should log the operation."""
        with caplog.at_level(logging.INFO):
            extract_pages(multipage_pdf, ranges=[(1, 3), (5, 7)], output_path=tmp_output)

        assert "extract" in caplog.text.lower()
        assert "6 pagine estratte" in caplog.text
