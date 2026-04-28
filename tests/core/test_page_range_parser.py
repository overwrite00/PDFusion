import pytest

from utils.exceptions import InvalidPageRangeError
from utils.page_range_parser import (
    format_page_ranges,
    parse_page_ranges,
    ranges_to_indices,
)


class TestParsePageRanges:
    def test_single_page(self):
        assert parse_page_ranges("3") == [(3, 3)]

    def test_range(self):
        assert parse_page_ranges("1-5") == [(1, 5)]

    def test_mixed(self):
        assert parse_page_ranges("1-3, 5, 7-9") == [(1, 3), (5, 5), (7, 9)]

    def test_spaces_ignored(self):
        assert parse_page_ranges("  2 - 4 , 6  ") == [(2, 4), (6, 6)]

    def test_last_keyword(self):
        result = parse_page_ranges("last", total_pages=10)
        assert result == [(10, 10)]

    def test_range_to_last(self):
        result = parse_page_ranges("5-last", total_pages=8)
        assert result == [(5, 8)]

    def test_invalid_reversed_range(self):
        with pytest.raises(InvalidPageRangeError):
            parse_page_ranges("5-3")

    def test_invalid_zero(self):
        with pytest.raises(InvalidPageRangeError):
            parse_page_ranges("0")

    def test_invalid_exceeds_total(self):
        with pytest.raises(InvalidPageRangeError):
            parse_page_ranges("15", total_pages=10)

    def test_invalid_text(self):
        with pytest.raises(InvalidPageRangeError):
            parse_page_ranges("abc")

    def test_empty_string(self):
        with pytest.raises(InvalidPageRangeError):
            parse_page_ranges("")


class TestRangesToIndices:
    def test_basic(self):
        assert ranges_to_indices([(1, 3)]) == [0, 1, 2]

    def test_mixed(self):
        result = ranges_to_indices([(1, 2), (5, 5)])
        assert result == [0, 1, 4]

    def test_deduplication(self):
        result = ranges_to_indices([(1, 3), (2, 4)])
        assert result == [0, 1, 2, 3]

    def test_sorted(self):
        result = ranges_to_indices([(5, 5), (1, 2)])
        assert result == [0, 1, 4]


class TestFormatPageRanges:
    def test_single(self):
        assert format_page_ranges([(3, 3)]) == "3"

    def test_range(self):
        assert format_page_ranges([(1, 5)]) == "1-5"

    def test_mixed(self):
        assert format_page_ranges([(1, 3), (5, 5), (7, 9)]) == "1-3, 5, 7-9"
