import pikepdf
import pytest

from core.watermark import (
    PageSelection,
    WatermarkConfig,
    WatermarkMode,
    WatermarkPosition,
    apply_watermark,
)


class TestTextWatermark:
    def test_center_diagonal(self, sample_pdf, tmp_output):
        cfg = WatermarkConfig(
            mode=WatermarkMode.TEXT,
            text="RISERVATO",
            position=WatermarkPosition.CENTER_DIAGONAL,
        )
        result = apply_watermark(sample_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_all_positions(self, sample_pdf, tmp_dir):
        for pos in WatermarkPosition:
            out = tmp_dir / f"wm_{pos.name}.pdf"
            cfg = WatermarkConfig(mode=WatermarkMode.TEXT, text="BOZZA", position=pos)
            result = apply_watermark(sample_pdf, out, cfg)
            assert result.exists()

    def test_custom_opacity(self, sample_pdf, tmp_output):
        cfg = WatermarkConfig(
            mode=WatermarkMode.TEXT,
            text="DRAFT",
            position=WatermarkPosition.CENTER_DIAGONAL,
            opacity=0.1,
        )
        result = apply_watermark(sample_pdf, tmp_output, cfg)
        assert result.exists()

    def test_page_selection_first_only(self, multipage_pdf, tmp_output):
        cfg = WatermarkConfig(
            mode=WatermarkMode.TEXT,
            text="BOZZA",
            position=WatermarkPosition.CENTER_DIAGONAL,
            page_selection=PageSelection.FIRST_ONLY,
        )
        result = apply_watermark(multipage_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_page_selection_last_only(self, multipage_pdf, tmp_output):
        cfg = WatermarkConfig(
            mode=WatermarkMode.TEXT,
            text="COPIA",
            position=WatermarkPosition.BOTTOM_RIGHT,
            page_selection=PageSelection.LAST_ONLY,
        )
        result = apply_watermark(multipage_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 10

    def test_empty_text_raises(self, sample_pdf, tmp_output):
        cfg = WatermarkConfig(
            mode=WatermarkMode.TEXT,
            text="",
            position=WatermarkPosition.CENTER_DIAGONAL,
        )
        from utils.exceptions import PDFusionError
        with pytest.raises(PDFusionError):
            apply_watermark(sample_pdf, tmp_output, cfg)


class TestImageWatermark:
    def test_png_watermark(self, sample_pdf, tmp_output, tmp_path):
        from PIL import Image
        img_path = tmp_path / "logo.png"
        img = Image.new("RGBA", (200, 100), (255, 0, 0, 128))
        img.save(img_path)

        cfg = WatermarkConfig(
            mode=WatermarkMode.IMAGE,
            image_path=img_path,
            position=WatermarkPosition.CENTER,
        )
        result = apply_watermark(sample_pdf, tmp_output, cfg)
        assert result.exists()

    def test_missing_image_raises(self, sample_pdf, tmp_output, tmp_path):
        from utils.exceptions import PDFusionError
        cfg = WatermarkConfig(
            mode=WatermarkMode.IMAGE,
            image_path=tmp_path / "nonexistent.png",
            position=WatermarkPosition.CENTER,
        )
        with pytest.raises((PDFusionError, FileNotFoundError, Exception)):
            apply_watermark(sample_pdf, tmp_output, cfg)
