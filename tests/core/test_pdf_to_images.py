import pytest

from core.pdf_to_images import ExportImagesConfig, ImageFormat, export_pages_as_images
from utils.exceptions import PDFusionError


class TestPdfToImages:
    def test_png_output(self, sample_pdf, tmp_dir):
        config = ExportImagesConfig(format=ImageFormat.PNG)
        files = export_pages_as_images(sample_pdf, tmp_dir, config=config)
        assert len(files) == 1
        assert files[0].suffix == ".png"

    def test_jpeg_output(self, sample_pdf, tmp_dir):
        config = ExportImagesConfig(format=ImageFormat.JPEG)
        files = export_pages_as_images(sample_pdf, tmp_dir, config=config)
        assert len(files) == 1
        assert files[0].suffix in (".jpg", ".jpeg")

    def test_multipage(self, multipage_pdf, tmp_dir):
        config = ExportImagesConfig(format=ImageFormat.PNG)
        files = export_pages_as_images(multipage_pdf, tmp_dir, config=config)
        assert len(files) == 10

    def test_custom_dpi(self, sample_pdf, tmp_dir):
        config_72 = ExportImagesConfig(format=ImageFormat.PNG, dpi=72)
        config_150 = ExportImagesConfig(format=ImageFormat.PNG, dpi=150)
        files_72 = export_pages_as_images(sample_pdf, tmp_dir / "72", config=config_72)
        files_150 = export_pages_as_images(sample_pdf, tmp_dir / "150", config=config_150)
        from PIL import Image
        img_72 = Image.open(files_72[0])
        img_150 = Image.open(files_150[0])
        assert img_150.width > img_72.width

    def test_files_created(self, sample_pdf, tmp_dir):
        config = ExportImagesConfig()
        files = export_pages_as_images(sample_pdf, tmp_dir, config=config)
        assert all(f.exists() for f in files)


class TestProtectedPdf:
    """Password utente della fixture: 'test123'."""

    def test_without_password_raises_a_clear_error(self, encrypted_pdf, tmp_dir):
        with pytest.raises(PDFusionError, match="Password"):
            export_pages_as_images(encrypted_pdf, tmp_dir, ExportImagesConfig())

    def test_wrong_password_raises_a_clear_error(self, encrypted_pdf, tmp_dir):
        with pytest.raises(PDFusionError, match="Password"):
            export_pages_as_images(encrypted_pdf, tmp_dir, ExportImagesConfig(), "sbagliata")

    def test_correct_password_works(self, encrypted_pdf, tmp_dir):
        files = export_pages_as_images(
            encrypted_pdf, tmp_dir, ExportImagesConfig(format=ImageFormat.PNG), "test123"
        )
        assert len(files) == 1 and files[0].exists()
