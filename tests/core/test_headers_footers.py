import pytest
import pikepdf
from core.headers_footers import (
    add_headers_footers,
    HeaderFooterConfig,
    HeaderFooterSection,
)


class TestHeadersFooters:
    def test_page_numbers_footer(self, multipage_pdf, tmp_output):
        cfg = HeaderFooterConfig(
            footer=HeaderFooterSection(center="{page} / {total}"),
        )
        result = add_headers_footers(multipage_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_all_variables(self, sample_pdf, tmp_output):
        cfg = HeaderFooterConfig(
            header=HeaderFooterSection(
                left="{title}",
                center="{author}",
                right="{date}",
            ),
            footer=HeaderFooterSection(
                left="{page}",
                right="{total}",
            ),
        )
        result = add_headers_footers(sample_pdf, tmp_output, cfg)
        assert result.exists()

    def test_empty_config(self, sample_pdf, tmp_output):
        cfg = HeaderFooterConfig()
        result = add_headers_footers(sample_pdf, tmp_output, cfg)
        assert result.exists()

    def test_page_range_string(self, multipage_pdf, tmp_output):
        cfg = HeaderFooterConfig(
            header=HeaderFooterSection(center="Pagina {page}"),
            page_range="1-5",
        )
        result = add_headers_footers(multipage_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_header_only(self, multipage_pdf, tmp_output):
        cfg = HeaderFooterConfig(
            header=HeaderFooterSection(center="Documento riservato"),
        )
        result = add_headers_footers(multipage_pdf, tmp_output, cfg)
        assert result.exists()
