import io

import pikepdf
import pymupdf
import pytest
from PIL import Image

from core.compress import CompressConfig, CompressPreset, compress


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


# ---------------------------------------------------------------------------
# Ricampionamento delle immagini ad alta risoluzione
#
# I PDF di fixture hanno immagini piccole (DPI effettivo sotto il target), quindi
# `_resample_images` le saltava tutte e il ramo che sostituisce l'immagine non veniva
# MAI eseguito: `doc.replace_image` non esiste in PyMuPDF (esiste solo `Page.replace_image`)
# e la compressione di qualsiasi PDF con un'immagine sopra il DPI target finiva in
# AttributeError. Questi test usano immagini davvero sopra il target.
# ---------------------------------------------------------------------------

_A4_WIDTH_PT = 595
# 1600 px su 595 pt = ~194 DPI effettivi: sopra il target EBOOK (150) di oltre il 10%.
_BIG_PX = 1600


def _pdf_with_big_image(path, mode="RGB"):
    noise = Image.effect_noise((_BIG_PX, _BIG_PX), 80).convert(mode)
    if mode == "RGBA":
        noise.putalpha(Image.linear_gradient("L").resize((_BIG_PX, _BIG_PX)))
    buf = io.BytesIO()
    noise.save(buf, format="PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=_A4_WIDTH_PT, height=842)
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(str(path))
    doc.close()
    return path


def _first_image_width(path) -> int:
    with pymupdf.open(str(path)) as doc:
        xref = doc[0].get_images(full=True)[0][0]
        return doc.extract_image(xref)["width"]


class TestCompressResamplesHighDpiImages:
    @pytest.mark.parametrize("mode", ["RGB", "RGBA"])
    def test_big_image_is_downsampled_and_pdf_stays_valid(self, tmp_path, mode):
        src = _pdf_with_big_image(tmp_path / "big.pdf", mode)
        out = tmp_path / "out.pdf"
        assert _first_image_width(src) == _BIG_PX

        result = compress(src, out, CompressConfig(preset=CompressPreset.EBOOK))

        assert result == out and out.stat().st_size < src.stat().st_size
        # 1600 px -> ~1240 px (150 DPI su una pagina di 595 pt)
        assert _first_image_width(out) <= 1300
        with pikepdf.open(out) as pdf:
            assert len(pdf.pages) == 1
        with pymupdf.open(str(out)) as doc:
            pix = doc[0].get_pixmap()  # la pagina si rende ancora
            assert pix.width > 0 and pix.height > 0

    def test_lower_preset_gives_a_smaller_image(self, tmp_path):
        src = _pdf_with_big_image(tmp_path / "big.pdf")
        ebook = tmp_path / "ebook.pdf"
        screen = tmp_path / "screen.pdf"
        compress(src, ebook, CompressConfig(preset=CompressPreset.EBOOK))
        compress(src, screen, CompressConfig(preset=CompressPreset.SCREEN))
        assert _first_image_width(screen) < _first_image_width(ebook) < _BIG_PX

    def test_flatten_annotations_iterates_every_page(self, multipage_pdf, tmp_output):
        cfg = CompressConfig(preset=CompressPreset.EBOOK, flatten_annotations=True)
        result = compress(multipage_pdf, tmp_output, cfg)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) > 1
