"""Test suite for page range validation and logging."""
import logging

import pytest

from utils.exceptions import PDFusionError
from utils.page_validator import (
    validate_page_index,
    validate_page_indices,
    validate_page_range,
    validate_page_ranges,
    log_page_operations,
)


class TestValidatePageIndex:
    """Test validate_page_index function."""

    def test_valid_page_index(self):
        """Valid page index should not raise."""
        validate_page_index(0, 10)
        validate_page_index(5, 10)
        validate_page_index(9, 10)

    def test_negative_index_valid(self):
        """Python-style negative indices should work."""
        validate_page_index(-1, 10)  # Last page
        validate_page_index(-5, 10)  # 5th from end
        validate_page_index(-10, 10)  # First page

    def test_negative_index_out_of_range(self):
        """Negative index beyond range should raise."""
        with pytest.raises(PDFusionError, match="non valido"):
            validate_page_index(-11, 10)

    def test_positive_index_out_of_range(self):
        """Page index >= total_pages should raise."""
        with pytest.raises(PDFusionError, match="non esiste"):
            validate_page_index(10, 10)

    def test_large_page_index(self):
        """Very large page index should raise with helpful message."""
        with pytest.raises(PDFusionError, match="non esiste.*PDF ha 5 pagine"):
            validate_page_index(100, 5)

    def test_non_integer_index(self):
        """Non-integer index should raise."""
        with pytest.raises(PDFusionError, match="numero intero"):
            validate_page_index(5.5, 10)  # type: ignore

    def test_empty_pdf(self):
        """Empty PDF validation should raise."""
        with pytest.raises(PDFusionError):
            validate_page_index(0, 0)


class TestValidatePageIndices:
    """Test validate_page_indices function."""

    def test_valid_indices(self):
        """Valid page indices should not raise."""
        validate_page_indices([0, 2, 4], 10)
        validate_page_indices([0], 1)

    def test_mixed_positive_negative_indices(self):
        """Mixed positive and negative indices should work."""
        validate_page_indices([0, -1, 5], 10)

    def test_empty_list(self):
        """Empty list should raise."""
        with pytest.raises(PDFusionError, match="vuota"):
            validate_page_indices([], 10)

    def test_single_invalid_index(self):
        """List with one invalid index should raise."""
        with pytest.raises(PDFusionError):
            validate_page_indices([0, 2, 15], 10)

    def test_all_indices_out_of_range(self):
        """List with all out-of-range indices should raise."""
        with pytest.raises(PDFusionError):
            validate_page_indices([100, 101, 102], 10)

    def test_duplicate_indices(self):
        """Duplicate indices should not raise (will be handled by set logic in caller)."""
        validate_page_indices([0, 2, 2, 5], 10)


class TestValidatePageRange:
    """Test validate_page_range function."""

    def test_valid_range(self):
        """Valid ranges should not raise."""
        validate_page_range(1, 5, 10)
        validate_page_range(1, 1, 10)
        validate_page_range(10, 10, 10)

    def test_range_single_page_pdf(self):
        """Range in single-page PDF."""
        validate_page_range(1, 1, 1)

    def test_start_less_than_one(self):
        """Start page < 1 should raise."""
        with pytest.raises(PDFusionError, match="inizio non valido"):
            validate_page_range(0, 5, 10)

    def test_end_before_start(self):
        """End < start should raise."""
        with pytest.raises(PDFusionError, match="non valido"):
            validate_page_range(5, 3, 10)

    def test_end_after_total(self):
        """End > total_pages should raise."""
        with pytest.raises(PDFusionError, match="supera il totale"):
            validate_page_range(5, 15, 10)

    def test_end_way_after_total(self):
        """End way beyond total should raise with suggestion."""
        with pytest.raises(PDFusionError, match="supera il totale.*pagina 10"):
            validate_page_range(1, 100, 10)


class TestValidatePageRanges:
    """Test validate_page_ranges function."""

    def test_valid_ranges(self):
        """Valid ranges should not raise."""
        validate_page_ranges([(1, 3), (5, 7), (10, 10)], 10)

    def test_overlapping_ranges(self):
        """Overlapping ranges should not raise (caller handles deduplication)."""
        validate_page_ranges([(1, 5), (3, 7)], 10)

    def test_empty_ranges_list(self):
        """Empty ranges list should raise."""
        with pytest.raises(PDFusionError, match="vuota"):
            validate_page_ranges([], 10)

    def test_single_range(self):
        """Single range should work."""
        validate_page_ranges([(5, 7)], 10)

    def test_multiple_ranges_with_one_invalid(self):
        """Multiple ranges with one invalid should raise."""
        with pytest.raises(PDFusionError):
            validate_page_ranges([(1, 3), (5, 15)], 10)

    def test_all_ranges_invalid(self):
        """All invalid ranges should raise."""
        with pytest.raises(PDFusionError):
            validate_page_ranges([(100, 150), (200, 300)], 10)


class TestLogPageOperations:
    """Test log_page_operations function."""

    def test_log_with_affected_pages(self, caplog):
        """Logging with affected pages should produce info message."""
        with caplog.at_level(logging.INFO):
            log_page_operations("rotate", 10, [0, 2, 4])

        assert "rotate" in caplog.text
        assert "10 pagine" in caplog.text

    def test_log_without_affected_pages(self, caplog):
        """Logging without affected pages should work."""
        with caplog.at_level(logging.INFO):
            log_page_operations("extract", 5)

        assert "extract" in caplog.text
        assert "5 pagine" in caplog.text

    def test_log_with_operation_details(self, caplog):
        """Logging with operation details should include them."""
        with caplog.at_level(logging.INFO):
            log_page_operations(
                "delete",
                10,
                [1, 2, 3],
                operation_details="3 pagine eliminate",
            )

        assert "delete" in caplog.text
        assert "3 pagine eliminate" in caplog.text

    def test_log_single_page(self, caplog):
        """Logging with single affected page."""
        with caplog.at_level(logging.INFO):
            log_page_operations("rotate", 10, [5])

        assert "rotate" in caplog.text
        assert "10 pagine" in caplog.text

    def test_log_consecutive_pages(self, caplog):
        """Logging with consecutive pages should format nicely."""
        with caplog.at_level(logging.INFO):
            log_page_operations("delete", 10, list(range(5)))

        assert "delete" in caplog.text

    def test_log_many_pages(self, caplog):
        """Logging with many pages should truncate display."""
        with caplog.at_level(logging.INFO):
            log_page_operations("rotate", 100, list(range(50)))

        assert "rotate" in caplog.text

    def test_log_set_input(self, caplog):
        """Logging should accept set of affected pages."""
        with caplog.at_level(logging.INFO):
            log_page_operations("delete", 10, {0, 2, 4})

        assert "delete" in caplog.text
        assert "10 pagine" in caplog.text
