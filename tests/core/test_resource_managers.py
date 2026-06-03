from __future__ import annotations

import gc
import io
import logging
import os

import psutil
import pytest
from PIL import Image

from core.headers_footers import HeaderFooterConfig, HeaderFooterSection, add_headers_footers
from core.images_to_pdf import FitMode, ImagesToPDFConfig, images_to_pdf
from core.watermark import WatermarkConfig, WatermarkMode, WatermarkPosition, apply_watermark
from utils.exceptions import PDFusionError

logger = logging.getLogger(__name__)


class TestWatermarkResourceManagement:
    """Test PIL Image e reportlab Canvas context managers in watermark.py"""

    def test_image_watermark_with_context_manager(self, tmp_path):
        """Happy path: Image aperto come context manager e chiuso correttamente"""
        # Setup
        img_path = tmp_path / "test_watermark.png"
        test_img = Image.new("RGB", (100, 100), color="red")
        test_img.save(img_path)

        pdf_path = tmp_path / "test.pdf"
        # Crea un PDF minimo per il test
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "Test")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = WatermarkConfig(
            mode=WatermarkMode.IMAGE,
            image_path=img_path,
            image_scale=0.3,
        )

        # Get initial file handle count
        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        # Execute
        result = apply_watermark(pdf_path, tmp_path / "output.pdf", config)

        # Verify
        assert result.exists()
        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "File handles leaked after watermark"

    def test_image_watermark_missing_file(self, tmp_path):
        """Error case: Image.open() fail con file mancante"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "Test")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = WatermarkConfig(
            mode=WatermarkMode.IMAGE,
            image_path=tmp_path / "nonexistent.png",
        )

        with pytest.raises(PDFusionError):
            apply_watermark(pdf_path, tmp_path / "output.pdf", config)

    def test_image_watermark_corrupted_image(self, tmp_path):
        """Error case: Image.UnidentifiedImageError per immagine corrotta"""
        # Create corrupted image file (zero-byte)
        img_path = tmp_path / "corrupted.png"
        img_path.write_bytes(b"")

        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "Test")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = WatermarkConfig(
            mode=WatermarkMode.IMAGE,
            image_path=img_path,
        )

        # Should not crash, just log warning (graceful degradation)
        result = apply_watermark(pdf_path, tmp_path / "output.pdf", config)
        assert result.exists()

    def test_text_watermark_canvas_cleanup(self, tmp_path):
        """Happy path: reportlab Canvas chiuso via try-finally"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "Test")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = WatermarkConfig(
            mode=WatermarkMode.TEXT,
            text="WATERMARK",
            font_size=36,
            position=WatermarkPosition.CENTER_DIAGONAL,
        )

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = apply_watermark(pdf_path, tmp_path / "output.pdf", config)

        assert result.exists()
        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "Canvas or BytesIO not cleaned up"

    def test_watermark_batch_no_leak(self, tmp_path):
        """Stress test: 10 watermark operations, no accumulation di handle"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "Test")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = WatermarkConfig(
            mode=WatermarkMode.TEXT,
            text="BATCH",
            position=WatermarkPosition.CENTER,
        )

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        for i in range(10):
            result = apply_watermark(
                pdf_path,
                tmp_path / f"output_{i}.pdf",
                config
            )
            assert result.exists()
            gc.collect()

        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            # Allow max 3 extra fds for batch operation
            assert final_fds <= initial_fds + 3, f"Leak detected: {initial_fds} -> {final_fds}"


class TestImagesToPDFResourceManagement:
    """Test PIL Image e reportlab Canvas context managers in images_to_pdf.py"""

    def test_images_to_pdf_pil_context_manager(self, tmp_path):
        """Happy path: Image.open() con context manager in loop"""
        # Create test images
        img_paths = []
        for i in range(3):
            img_path = tmp_path / f"test_img_{i}.png"
            test_img = Image.new("RGB", (200 + i * 50, 300), color="blue")
            test_img.save(img_path)
            img_paths.append(img_path)

        pdf_path = tmp_path / "output.pdf"

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = images_to_pdf(img_paths, pdf_path)

        assert result.exists()
        assert result.stat().st_size > 0

        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "PIL images not released"

    def test_images_to_pdf_bytesio_cleanup(self, tmp_path):
        """Happy path: img_buf BytesIO chiuso via finally in loop"""
        img_paths = []
        for i in range(2):
            img_path = tmp_path / f"test_img_{i}.jpg"
            test_img = Image.new("RGB", (150, 200), color="green")
            test_img.save(img_path)
            img_paths.append(img_path)

        pdf_path = tmp_path / "output.pdf"
        config = ImagesToPDFConfig(fit_mode=FitMode.FIT_PAGE)

        process = psutil.Process(os.getpid())
        initial_mem = process.memory_info().rss

        result = images_to_pdf(img_paths, pdf_path, config)

        assert result.exists()
        gc.collect()
        final_mem = process.memory_info().rss

        # Memory growth should be minimal (< 10MB for 2 small images)
        mem_growth_mb = (final_mem - initial_mem) / (1024 * 1024)
        assert mem_growth_mb < 10, f"Memory not released: {mem_growth_mb}MB growth"

    def test_images_to_pdf_canvas_cleanup(self, tmp_path):
        """Happy path: reportlab Canvas con try-finally"""
        img_path = tmp_path / "test_img.png"
        test_img = Image.new("RGB", (100, 150), color="yellow")
        test_img.save(img_path)

        pdf_path = tmp_path / "output.pdf"

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = images_to_pdf([img_path], pdf_path)

        assert result.exists()
        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "Canvas or buffers not cleaned"

    def test_images_to_pdf_missing_image(self, tmp_path):
        """Error case: Image.open() fail con file mancante"""
        img_path = tmp_path / "nonexistent.png"
        pdf_path = tmp_path / "output.pdf"

        with pytest.raises(PDFusionError):
            images_to_pdf([img_path], pdf_path)

    def test_images_to_pdf_batch_operations(self, tmp_path):
        """Stress test: 20 iterazioni di conversione, verifica no leak"""
        img_path = tmp_path / "test_img.png"
        test_img = Image.new("RGB", (100, 100), color="red")
        test_img.save(img_path)

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        initial_mem = process.memory_info().rss

        for i in range(20):
            pdf_path = tmp_path / f"output_{i}.pdf"
            result = images_to_pdf([img_path], pdf_path)
            assert result.exists()
            gc.collect()

        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        final_mem = process.memory_info().rss

        if initial_fds >= 0:
            assert final_fds <= initial_fds + 3, f"Leak after 20 iterations: {initial_fds} -> {final_fds}"

        mem_growth_mb = (final_mem - initial_mem) / (1024 * 1024)
        assert mem_growth_mb < 20, f"Memory leak: {mem_growth_mb}MB growth after 20 ops"

    def test_images_to_pdf_rgba_conversion(self, tmp_path):
        """Happy path: RGBA to RGB conversion con context manager"""
        img_path = tmp_path / "rgba_img.png"
        test_img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 255))
        test_img.save(img_path)

        pdf_path = tmp_path / "output.pdf"

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = images_to_pdf([img_path], pdf_path)

        assert result.exists()
        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "RGBA conversion leaked resources"


class TestHeadersFootersResourceManagement:
    """Test reportlab Canvas context managers in headers_footers.py"""

    def test_headers_footers_canvas_cleanup(self, tmp_path):
        """Happy path: reportlab Canvas con try-finally in _generate_overlay"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "Test PDF")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = HeaderFooterConfig(
            header=HeaderFooterSection(left="Header Left", right="Header Right"),
            footer=HeaderFooterSection(center="Page {page} of {total}"),
        )

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = add_headers_footers(pdf_path, tmp_path / "output.pdf", config)

        assert result.exists()
        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "Canvas or BytesIO not cleaned"

    def test_headers_footers_bytesio_cleanup(self, tmp_path):
        """Happy path: buf.close() esplicita nel finally"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf)
        c.drawString(100, 750, "Test")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = HeaderFooterConfig(
            footer=HeaderFooterSection(right="Footer")
        )

        process = psutil.Process(os.getpid())
        initial_mem = process.memory_info().rss

        result = add_headers_footers(pdf_path, tmp_path / "output.pdf", config)

        assert result.exists()
        gc.collect()
        final_mem = process.memory_info().rss

        mem_growth_mb = (final_mem - initial_mem) / (1024 * 1024)
        assert mem_growth_mb < 5, f"Memory not released: {mem_growth_mb}MB"

    def test_headers_footers_batch_pages(self, tmp_path):
        """Stress test: PDF con 50 pagine, verifica memory usage"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(612, 792))
        for i in range(50):
            c.drawString(100, 750, f"Page {i+1}")
            c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = HeaderFooterConfig(
            header=HeaderFooterSection(center="Document Header"),
            footer=HeaderFooterSection(center="Page {page}/{total}"),
        )

        process = psutil.Process(os.getpid())
        initial_mem = process.memory_info().rss
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = add_headers_footers(pdf_path, tmp_path / "output.pdf", config)

        assert result.exists()
        gc.collect()
        final_mem = process.memory_info().rss
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        mem_growth_mb = (final_mem - initial_mem) / (1024 * 1024)
        assert mem_growth_mb < 30, f"Memory leak on 50-page doc: {mem_growth_mb}MB"

        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "FD leak on batch pages"

    def test_headers_footers_different_first_page(self, tmp_path):
        """Happy path: different_first_page flag con resource cleanup"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf)
        c.drawString(100, 750, "Page 1")
        c.showPage()
        c.drawString(100, 750, "Page 2")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        config = HeaderFooterConfig(
            different_first_page=True,
            first_page_header=HeaderFooterSection(center="First Page"),
            header=HeaderFooterSection(center="Normal Header"),
            footer=HeaderFooterSection(center="Footer"),
        )

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = add_headers_footers(pdf_path, tmp_path / "output.pdf", config)

        assert result.exists()
        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 2, "Resource leak with different_first_page"


class TestEdgeCases:
    """Edge cases per resource management"""

    def test_zero_byte_image_handled_gracefully(self, tmp_path):
        """Edge case: zero-byte image file"""
        img_path = tmp_path / "zero.png"
        img_path.write_bytes(b"")

        with pytest.raises(PDFusionError):
            images_to_pdf([img_path], tmp_path / "output.pdf")

    def test_very_large_image_simulation(self, tmp_path):
        """Edge case: large image (100KB PNG)"""
        img_path = tmp_path / "large.png"
        # Create large image: 1000x1000
        test_img = Image.new("RGB", (1000, 1000), color="cyan")
        test_img.save(img_path, quality=95)

        pdf_path = tmp_path / "output.pdf"

        process = psutil.Process(os.getpid())
        initial_mem = process.memory_info().rss

        result = images_to_pdf([img_path], pdf_path)

        assert result.exists()
        gc.collect()
        final_mem = process.memory_info().rss

        # Even large image should not leak more than 50MB
        mem_growth_mb = (final_mem - initial_mem) / (1024 * 1024)
        assert mem_growth_mb < 50, f"Excessive memory for large image: {mem_growth_mb}MB"

    def test_empty_headers_footers_no_unnecessary_resources(self, tmp_path):
        """Edge case: empty config doesn't allocate unnecessary resources"""
        pdf_path = tmp_path / "test.pdf"
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf)
        c.drawString(100, 750, "Test")
        c.showPage()
        c.save()
        buf.seek(0)
        pdf_path.write_bytes(buf.getvalue())

        # Empty config = no overlay generation
        config = HeaderFooterConfig()

        process = psutil.Process(os.getpid())
        initial_fds = process.num_fds() if hasattr(process, 'num_fds') else -1

        result = add_headers_footers(pdf_path, tmp_path / "output.pdf", config)

        assert result.exists()
        # Should just copy file without overlay generation
        gc.collect()
        final_fds = process.num_fds() if hasattr(process, 'num_fds') else -1
        if initial_fds >= 0:
            assert final_fds <= initial_fds + 1, "Empty config allocated unnecessary resources"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
