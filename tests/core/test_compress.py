import pytest
import pikepdf
from core.compress import compress, CompressConfig, CompressPreset


class TestCompress:
    def test_screen_preset(self, with_images_pdf, tmp_output):
        cfg = CompressConfig(preset=CompressPreset.SCREEN)
        result = compress(with_images_pdf, tmp_output, cfg)
        assert result.exists()
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_ebook_preset(self, with_images_pdf, tmp_output):
        cfg = CompressConfig(preset=CompressPreset.EBOOK)
        result = compress(with_images_pdf, tmp_output, cfg)
        assert result.exists()

    def test_ebook_is_default(self):
        cfg = CompressConfig()
        assert cfg.preset == CompressPreset.EBOOK

    def test_remove_metadata(self, sample_pdf, tmp_output):
        cfg = CompressConfig(preset=CompressPreset.EBOOK, remove_metadata=True)
        result = compress(sample_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            docinfo = pdf.docinfo
            assert str(docinfo.get("/Author", "")) == ""

    def test_custom_preset(self, with_images_pdf, tmp_output):
        cfg = CompressConfig(
            preset=CompressPreset.CUSTOM,
            custom_dpi=100,
            custom_jpeg_quality=70,
        )
        result = compress(with_images_pdf, tmp_output, cfg)
        assert result.exists()

    def test_sample_without_images(self, sample_pdf, tmp_output):
        cfg = CompressConfig(preset=CompressPreset.EBOOK)
        result = compress(sample_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_flatten_annotations(self, sample_pdf, tmp_output):
        cfg = CompressConfig(preset=CompressPreset.EBOOK, flatten_annotations=True)
        result = compress(sample_pdf, tmp_output, cfg)
        assert result.exists()
