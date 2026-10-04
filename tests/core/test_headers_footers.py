import pikepdf
import pytest

from core.headers_footers import (
    HeaderFooterConfig,
    HeaderFooterSection,
    add_headers_footers,
)
from utils.exceptions import PDFusionError


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


class TestProtectedPdf:
    """PDF protetto da password (la fixture ha password utente 'test123').

    Senza password ``doc.metadata`` è ``None`` (documento cifrato non autenticato): il codice
    faceva ``meta.get(...)`` e falliva con ``AttributeError`` invece di chiedere la password,
    a differenza del caso "password errata", che già dava un ``PDFusionError`` chiaro.
    """

    @staticmethod
    def _config() -> HeaderFooterConfig:
        return HeaderFooterConfig(header=HeaderFooterSection(center="Pagina {page}"))

    def test_without_password_raises_a_clear_error(self, encrypted_pdf, tmp_output):
        with pytest.raises(PDFusionError, match="Password"):
            add_headers_footers(encrypted_pdf, tmp_output, self._config())
        assert not tmp_output.exists()

    def test_wrong_password_raises_a_clear_error(self, encrypted_pdf, tmp_output):
        with pytest.raises(PDFusionError, match="Password"):
            add_headers_footers(encrypted_pdf, tmp_output, self._config(), password="sbagliata")

    def test_correct_password_works(self, encrypted_pdf, tmp_output):
        result = add_headers_footers(
            encrypted_pdf, tmp_output, self._config(), password="test123"
        )
        assert result.exists()
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1
