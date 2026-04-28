from core.pdf_to_images import ImageFormat, pdf_to_images


class TestPdfToImages:
    def test_png_output(self, sample_pdf, tmp_dir):
        files = pdf_to_images(sample_pdf, tmp_dir, fmt=ImageFormat.PNG)
        assert len(files) == 1
        assert files[0].suffix == ".png"

    def test_jpeg_output(self, sample_pdf, tmp_dir):
        files = pdf_to_images(sample_pdf, tmp_dir, fmt=ImageFormat.JPEG)
        assert len(files) == 1
        assert files[0].suffix in (".jpg", ".jpeg")

    def test_multipage(self, multipage_pdf, tmp_dir):
        files = pdf_to_images(multipage_pdf, tmp_dir, fmt=ImageFormat.PNG)
        assert len(files) == 10

    def test_custom_dpi(self, sample_pdf, tmp_dir):
        files_72 = pdf_to_images(sample_pdf, tmp_dir / "72", fmt=ImageFormat.PNG, dpi=72)
        files_150 = pdf_to_images(sample_pdf, tmp_dir / "150", fmt=ImageFormat.PNG, dpi=150)
        from PIL import Image
        img_72 = Image.open(files_72[0])
        img_150 = Image.open(files_150[0])
        assert img_150.width > img_72.width

    def test_files_created(self, sample_pdf, tmp_dir):
        files = pdf_to_images(sample_pdf, tmp_dir)
        assert all(f.exists() for f in files)
