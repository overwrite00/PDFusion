import pikepdf
import pytest

from core.license_page import LicenseConfig, LicenseType, insert_license_page


class TestInsertLicensePage:
    def test_adds_page_at_start(self, sample_pdf, tmp_output):
        cfg = LicenseConfig(license_type=LicenseType.MIT, author="Test Author", year=2024)
        result = insert_license_page(sample_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_all_license_types(self, sample_pdf, tmp_dir):
        for lt in LicenseType:
            out = tmp_dir / f"lic_{lt.name}.pdf"
            cfg = LicenseConfig(license_type=lt, author="Author", year=2024)
            result = insert_license_page(sample_pdf, out, cfg)
            with pikepdf.open(result) as pdf:
                assert len(pdf.pages) == 2, f"Fallito per {lt.name}"

    def test_missing_author_raises(self, sample_pdf, tmp_output):
        cfg = LicenseConfig(license_type=LicenseType.MIT, author="")
        from utils.exceptions import PDFusionError
        with pytest.raises(PDFusionError):
            insert_license_page(sample_pdf, tmp_output, cfg)

    def test_multipage_plus_one(self, multipage_pdf, tmp_output):
        cfg = LicenseConfig(license_type=LicenseType.CC0, author="Chiunque")
        result = insert_license_page(multipage_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 11

    def test_document_title_accepted(self, sample_pdf, tmp_output):
        cfg = LicenseConfig(
            license_type=LicenseType.CC_BY,
            author="A. Rossi",
            year=2025,
            document_title="Documento di Test",
        )
        result = insert_license_page(sample_pdf, tmp_output, cfg)
        assert result.exists()
