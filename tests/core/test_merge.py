import pytest
import pikepdf
from core.merge import merge


class TestMerge:
    def test_merge_two(self, sample_pdf, multipage_pdf, tmp_output):
        result = merge([sample_pdf, multipage_pdf], tmp_output)
        assert result == tmp_output
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 11  # 1 + 10

    def test_merge_same_file_twice(self, sample_pdf, tmp_output):
        result = merge([sample_pdf, sample_pdf], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_merge_single(self, multipage_pdf, tmp_output):
        result = merge([multipage_pdf], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_merge_empty_list_raises(self, tmp_output):
        with pytest.raises(ValueError):
            merge([], tmp_output)

    def test_merge_with_encrypted(self, sample_pdf, encrypted_pdf, tmp_output):
        result = merge([sample_pdf, encrypted_pdf], tmp_output, passwords=[None, "test123"])
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_output_created(self, sample_pdf, multipage_pdf, tmp_output):
        assert not tmp_output.exists()
        merge([sample_pdf, multipage_pdf], tmp_output)
        assert tmp_output.exists()
