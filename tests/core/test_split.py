import pytest
import pikepdf
from pathlib import Path
from core.split import split_every_n, split_ranges
from utils.exceptions import InvalidPageRangeError


class TestSplitEveryN:
    def test_split_every_1(self, multipage_pdf, tmp_dir):
        files = split_every_n(multipage_pdf, 1, tmp_dir)
        assert len(files) == 10
        for f in files:
            with pikepdf.open(f) as pdf:
                assert len(pdf.pages) == 1

    def test_split_every_3(self, multipage_pdf, tmp_dir):
        files = split_every_n(multipage_pdf, 3, tmp_dir)
        # 10 pages: chunks of 3, 3, 3, 1
        assert len(files) == 4
        with pikepdf.open(files[0]) as pdf:
            assert len(pdf.pages) == 3
        with pikepdf.open(files[-1]) as pdf:
            assert len(pdf.pages) == 1

    def test_split_entire(self, multipage_pdf, tmp_dir):
        files = split_every_n(multipage_pdf, 10, tmp_dir)
        assert len(files) == 1

    def test_output_filenames(self, multipage_pdf, tmp_dir):
        files = split_every_n(multipage_pdf, 5, tmp_dir)
        assert files[0].name.endswith("_part001.pdf")
        assert files[1].name.endswith("_part002.pdf")

    def test_n_zero_raises(self, multipage_pdf, tmp_dir):
        with pytest.raises(ValueError):
            split_every_n(multipage_pdf, 0, tmp_dir)

    def test_encrypted(self, encrypted_pdf, tmp_dir):
        files = split_every_n(encrypted_pdf, 1, tmp_dir, password="test123")
        assert len(files) == 1


class TestSplitRanges:
    def test_basic_ranges(self, multipage_pdf, tmp_dir):
        files = split_ranges(multipage_pdf, [(1, 3), (7, 10)], tmp_dir)
        assert len(files) == 2
        with pikepdf.open(files[0]) as pdf:
            assert len(pdf.pages) == 3
        with pikepdf.open(files[1]) as pdf:
            assert len(pdf.pages) == 4

    def test_single_page_range(self, multipage_pdf, tmp_dir):
        files = split_ranges(multipage_pdf, [(5, 5)], tmp_dir)
        assert len(files) == 1
        with pikepdf.open(files[0]) as pdf:
            assert len(pdf.pages) == 1

    def test_out_of_bounds_raises(self, sample_pdf, tmp_dir):
        with pytest.raises(InvalidPageRangeError):
            split_ranges(sample_pdf, [(1, 5)], tmp_dir)
