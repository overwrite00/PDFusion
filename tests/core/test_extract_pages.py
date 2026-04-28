import pikepdf

from core.extract_pages import extract_pages


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
