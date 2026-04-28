import pytest
import pikepdf
from core.insert_page import insert_blank_page, insert_from_pdf


class TestInsertBlankPage:
    def test_insert_at_start(self, sample_pdf, tmp_output):
        result = insert_blank_page(sample_pdf, 1, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_insert_at_end(self, multipage_pdf, tmp_output):
        result = insert_blank_page(multipage_pdf, 11, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 11

    def test_insert_in_middle(self, multipage_pdf, tmp_output):
        result = insert_blank_page(multipage_pdf, 5, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 11

    def test_custom_page_size_letter(self, sample_pdf, tmp_output):
        result = insert_blank_page(sample_pdf, 1, tmp_output, page_size="Letter")
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_position_clamped_to_end(self, sample_pdf, tmp_output):
        # Posizione > total+1 viene clampata alla fine
        result = insert_blank_page(sample_pdf, 99, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2


class TestInsertFromPdf:
    def test_insert_single_page(self, sample_pdf, multipage_pdf, tmp_output):
        result = insert_from_pdf(
            sample_pdf,
            multipage_pdf,
            [(1, 1)],
            position=1,
            output_path=tmp_output,
        )
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_insert_range(self, sample_pdf, multipage_pdf, tmp_output):
        result = insert_from_pdf(
            sample_pdf,
            multipage_pdf,
            [(1, 3)],
            position=2,
            output_path=tmp_output,
        )
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 4

    def test_insert_all_pages_empty_range(self, sample_pdf, multipage_pdf, tmp_output):
        # Lista range vuota = tutte le pagine del sorgente
        result = insert_from_pdf(
            sample_pdf,
            multipage_pdf,
            [],
            position=1,
            output_path=tmp_output,
        )
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 11
