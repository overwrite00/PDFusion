
import pikepdf
import pytest
from PIL import Image

from core.images_to_pdf import images_to_pdf
from utils.exceptions import PDFusionError


@pytest.fixture
def sample_images(tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"img_{i:02d}.png"
        Image.new("RGB", (400, 300), color=(i * 80, 100, 200)).save(p)
        paths.append(p)
    return paths


class TestImagesToPdf:
    def test_creates_pdf(self, sample_images, tmp_output):
        result = images_to_pdf(sample_images, tmp_output)
        assert result.exists()

    def test_page_count(self, sample_images, tmp_output):
        result = images_to_pdf(sample_images, tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 3

    def test_single_image(self, sample_images, tmp_output):
        result = images_to_pdf([sample_images[0]], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_empty_list_raises(self, tmp_output):
        with pytest.raises(PDFusionError):
            images_to_pdf([], tmp_output)

    def test_mixed_formats(self, tmp_path, tmp_output):
        png = tmp_path / "img.png"
        jpg = tmp_path / "img.jpg"
        Image.new("RGB", (300, 200), (255, 0, 0)).save(png)
        Image.new("RGB", (300, 200), (0, 255, 0)).save(jpg, format="JPEG")
        result = images_to_pdf([png, jpg], tmp_output)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2
