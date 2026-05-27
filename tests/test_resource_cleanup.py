"""
Test suite per validare cleanup di risorse (file handles) nei moduli core.

Testa che fitz.Document e pikepdf.Pdf siano correttamente chiusi anche in caso
di eccezione, prevenendo resource leak durante batch operations e PDF grandi.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Assumiamo che psutil sia disponibile per contare file handles
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

import fitz
import pikepdf

from core.compress import compress, CompressConfig, CompressPreset
from core.pdf_to_images import export_pages_as_images, ExportImagesConfig, ImageFormat
from core.headers_footers import add_headers_footers, HeaderFooterConfig, HeaderFooterSection
from utils.exceptions import PDFusionError, UnsupportedFormatError

logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Crea una directory temporanea per test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def valid_pdf(temp_dir: Path) -> Path:
    """Crea un PDF valido di test con 3 pagine."""
    pdf_path = temp_dir / "valid.pdf"
    doc = fitz.open()

    for i in range(3):
        page = doc.new_page()
        text = f"Test Page {i + 1}"
        page.insert_text((50, 50), text, fontsize=12)

    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def pdf_with_image(temp_dir: Path) -> Path:
    """Crea un PDF con immagine embedded."""
    pdf_path = temp_dir / "with_image.pdf"
    doc = fitz.open()

    page = doc.new_page()
    # Crea una semplice immagine di test
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 200))
    pix.fill_rect(fitz.IRect(0, 0, 100, 100), (255, 0, 0))  # Rosso

    # Inserisci l'immagine nella pagina
    page.insert_image(fitz.Rect(50, 50, 250, 250), pixmap=pix)

    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def corrupt_pdf(temp_dir: Path) -> Path:
    """Crea un file PDF corrotto."""
    pdf_path = temp_dir / "corrupt.pdf"
    # Scrivi dati non-PDF
    pdf_path.write_bytes(b"This is not a PDF file")
    return pdf_path


@pytest.fixture
def missing_pdf() -> Path:
    """Percorso a un PDF che non esiste."""
    return Path("/nonexistent/path/missing.pdf")


def count_open_file_handles() -> int:
    """Conta il numero di file handles aperti dal processo corrente."""
    if not PSUTIL_AVAILABLE:
        return -1
    try:
        process = psutil.Process()
        return len(process.open_files())
    except Exception:
        return -1


# ============================================================================
# TESTS: compress.py
# ============================================================================

class TestCompressResourceCleanup:
    """Tests per il cleanup di risorse in compress.py"""

    def test_compress_happy_path_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: PDF valido compresso correttamente, documenti chiusi."""
        output_pdf = temp_dir / "compressed.pdf"
        config = CompressConfig(preset=CompressPreset.EBOOK)

        handles_before = count_open_file_handles()

        result = compress(valid_pdf, output_pdf, config=config)

        handles_after = count_open_file_handles()

        # Verifiche
        assert result == output_pdf
        assert output_pdf.exists()
        assert output_pdf.stat().st_size > 0

        # Se psutil disponibile, verifica no leak
        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 1, \
                f"File handle leak: {handles_before} → {handles_after}"

    def test_compress_with_image_closes_documents(
        self, pdf_with_image: Path, temp_dir: Path
    ) -> None:
        """Test: PDF con immagine compresso, documenti chiusi."""
        output_pdf = temp_dir / "compressed_img.pdf"
        config = CompressConfig(preset=CompressPreset.SCREEN)

        handles_before = count_open_file_handles()

        result = compress(pdf_with_image, output_pdf, config=config)

        handles_after = count_open_file_handles()

        assert result == output_pdf
        assert output_pdf.exists()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 1

    def test_compress_corrupt_pdf_closes_documents(
        self, corrupt_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: PDF corrotto solleva eccezione, nessun leak."""
        output_pdf = temp_dir / "out.pdf"
        config = CompressConfig()

        handles_before = count_open_file_handles()

        with pytest.raises(UnsupportedFormatError):
            compress(corrupt_pdf, output_pdf, config=config)

        handles_after = count_open_file_handles()

        # Nessun handle dovrebbe rimanere aperto
        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before, \
                f"Handle leak after exception: {handles_before} → {handles_after}"

    def test_compress_missing_pdf_closes_documents(
        self, missing_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: PDF mancante solleva eccezione, nessun leak."""
        output_pdf = temp_dir / "out.pdf"

        handles_before = count_open_file_handles()

        with pytest.raises(PDFusionError, match="File non trovato"):
            compress(missing_pdf, output_pdf)

        handles_after = count_open_file_handles()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_compress_exception_during_resample_closes_documents(
        self, pdf_with_image: Path, temp_dir: Path
    ) -> None:
        """Test: Eccezione durante _resample_images chiude doc."""
        output_pdf = temp_dir / "out.pdf"
        config = CompressConfig()

        handles_before = count_open_file_handles()

        # Mock _resample_images per sollevare eccezione
        with patch('core.compress._resample_images', side_effect=RuntimeError("Mock error")):
            with pytest.raises(RuntimeError):
                compress(pdf_with_image, output_pdf, config=config)

        handles_after = count_open_file_handles()

        # Doc dovrebbe essere chiuso dal finally block
        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_compress_exception_during_flatten_closes_documents(
        self, pdf_with_image: Path, temp_dir: Path
    ) -> None:
        """Test: Eccezione durante _flatten_annotations chiude doc."""
        output_pdf = temp_dir / "out.pdf"
        config = CompressConfig(flatten_annotations=True)

        handles_before = count_open_file_handles()

        with patch('core.compress._flatten_annotations', side_effect=ValueError("Mock error")):
            with pytest.raises(ValueError):
                compress(pdf_with_image, output_pdf, config=config)

        handles_after = count_open_file_handles()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_compress_exception_during_pikepdf_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Eccezione durante pikepdf.save chiude entrambi i doc."""
        output_pdf = temp_dir / "out.pdf"
        config = CompressConfig()

        handles_before = count_open_file_handles()

        with patch('pikepdf.Pdf.save', side_effect=IOError("Mock save error")):
            with pytest.raises(IOError):
                compress(valid_pdf, output_pdf, config=config)

        handles_after = count_open_file_handles()

        # Entrambi i documenti (fitz + pikepdf) dovrebbero essere chiusi
        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before


# ============================================================================
# TESTS: pdf_to_images.py
# ============================================================================

class TestExportImagesResourceCleanup:
    """Tests per il cleanup di risorse in pdf_to_images.py"""

    def test_export_happy_path_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Esportazione valida chiude document."""
        output_dir = temp_dir / "images"
        config = ExportImagesConfig(format=ImageFormat.PNG, dpi=150)

        handles_before = count_open_file_handles()

        result = export_pages_as_images(valid_pdf, output_dir, config=config)

        handles_after = count_open_file_handles()

        assert len(result) == 3  # 3 pagine
        assert all(p.exists() for p in result)

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 1

    def test_export_corrupt_pdf_closes_documents(
        self, corrupt_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: PDF corrotto solleva eccezione, no leak."""
        output_dir = temp_dir / "images"

        handles_before = count_open_file_handles()

        with pytest.raises(UnsupportedFormatError):
            export_pages_as_images(corrupt_pdf, output_dir)

        handles_after = count_open_file_handles()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_export_missing_pdf_closes_documents(
        self, missing_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: PDF mancante solleva eccezione, no leak."""
        output_dir = temp_dir / "images"

        handles_before = count_open_file_handles()

        with pytest.raises(UnsupportedFormatError):
            export_pages_as_images(missing_pdf, output_dir)

        handles_after = count_open_file_handles()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_export_exception_during_pixmap_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Eccezione durante get_pixmap chiude doc."""
        output_dir = temp_dir / "images"

        handles_before = count_open_file_handles()

        with patch('fitz.Page.get_pixmap', side_effect=RuntimeError("Mock pixmap error")):
            with pytest.raises(RuntimeError):
                export_pages_as_images(valid_pdf, output_dir)

        handles_after = count_open_file_handles()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_export_exception_during_save_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Eccezione durante pixmap.save chiude doc."""
        output_dir = temp_dir / "images"

        handles_before = count_open_file_handles()

        with patch('fitz.Pixmap.save', side_effect=IOError("Mock save error")):
            with pytest.raises(IOError):
                export_pages_as_images(valid_pdf, output_dir)

        handles_after = count_open_file_handles()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_export_with_page_range_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Esportazione con page_range chiude doc."""
        output_dir = temp_dir / "images"
        config = ExportImagesConfig(page_range="1-2")

        handles_before = count_open_file_handles()

        result = export_pages_as_images(valid_pdf, output_dir, config=config)

        handles_after = count_open_file_handles()

        assert len(result) == 2

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 1

    def test_export_jpeg_format_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Esportazione JPEG chiude doc."""
        output_dir = temp_dir / "images"
        config = ExportImagesConfig(format=ImageFormat.JPEG, jpeg_quality=80)

        handles_before = count_open_file_handles()

        result = export_pages_as_images(valid_pdf, output_dir, config=config)

        handles_after = count_open_file_handles()

        assert len(result) == 3
        assert all(p.suffix == ".jpeg" for p in result)

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 1


# ============================================================================
# TESTS: headers_footers.py
# ============================================================================

class TestHeadersFootersResourceCleanup:
    """Tests per il cleanup di risorse in headers_footers.py"""

    def test_add_headers_footers_happy_path_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Aggiunta header/footer valida chiude documenti."""
        output_pdf = temp_dir / "with_headers.pdf"
        config = HeaderFooterConfig(
            header=HeaderFooterSection(center="Header Text"),
            footer=HeaderFooterSection(right="Page {page} of {total}")
        )

        handles_before = count_open_file_handles()

        result = add_headers_footers(valid_pdf, output_pdf, config)

        handles_after = count_open_file_handles()

        assert result == output_pdf
        assert output_pdf.exists()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 2  # +2 per main doc + overlays

    def test_add_headers_footers_corrupt_pdf_closes_documents(
        self, corrupt_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: PDF corrotto solleva eccezione, no leak."""
        output_pdf = temp_dir / "out.pdf"
        config = HeaderFooterConfig(
            header=HeaderFooterSection(center="Test")
        )

        handles_before = count_open_file_handles()

        with pytest.raises(UnsupportedFormatError):
            add_headers_footers(corrupt_pdf, output_pdf, config)

        handles_after = count_open_file_handles()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_add_headers_footers_exception_during_overlay_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Eccezione durante _generate_overlay chiude main doc."""
        output_pdf = temp_dir / "out.pdf"
        config = HeaderFooterConfig(
            header=HeaderFooterSection(center="Test")
        )

        handles_before = count_open_file_handles()

        with patch('core.headers_footers._generate_overlay', side_effect=RuntimeError("Mock overlay error")):
            with pytest.raises(RuntimeError):
                add_headers_footers(valid_pdf, output_pdf, config)

        handles_after = count_open_file_handles()

        # Main doc dovrebbe essere chiuso dal finally
        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_add_headers_footers_exception_during_show_pdf_page_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Eccezione durante show_pdf_page chiude documenti."""
        output_pdf = temp_dir / "out.pdf"
        config = HeaderFooterConfig(
            header=HeaderFooterSection(center="Test")
        )

        handles_before = count_open_file_handles()

        with patch('fitz.Page.show_pdf_page', side_effect=ValueError("Mock show error")):
            with pytest.raises(ValueError):
                add_headers_footers(valid_pdf, output_pdf, config)

        handles_after = count_open_file_handles()

        # Sia main che overlay docs dovrebbero essere chiusi
        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_add_headers_footers_no_content_copies_file(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Config senza contenuto copia file senza modifiche."""
        output_pdf = temp_dir / "copy.pdf"
        config = HeaderFooterConfig()  # Nessun contenuto

        handles_before = count_open_file_handles()

        result = add_headers_footers(valid_pdf, output_pdf, config)

        handles_after = count_open_file_handles()

        assert result == output_pdf
        assert output_pdf.exists()

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            # Questo percorso non apre PDF via fitz
            assert handles_after <= handles_before + 1

    def test_add_headers_footers_different_first_page_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Header/footer diversi per prima pagina, documenti chiusi."""
        output_pdf = temp_dir / "out.pdf"
        config = HeaderFooterConfig(
            header=HeaderFooterSection(center="Normal Header"),
            first_page_header=HeaderFooterSection(center="First Page Header"),
            different_first_page=True
        )

        handles_before = count_open_file_handles()

        result = add_headers_footers(valid_pdf, output_pdf, config)

        handles_after = count_open_file_handles()

        assert result == output_pdf

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 2

    def test_add_headers_footers_different_odd_even_closes_documents(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Header/footer diversi per pari/dispari, documenti chiusi."""
        output_pdf = temp_dir / "out.pdf"
        config = HeaderFooterConfig(
            header=HeaderFooterSection(center="Odd Header"),
            even_header=HeaderFooterSection(center="Even Header"),
            different_odd_even=True
        )

        handles_before = count_open_file_handles()

        result = add_headers_footers(valid_pdf, output_pdf, config)

        handles_after = count_open_file_handles()

        assert result == output_pdf

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 2


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests per edge cases di resource cleanup."""

    def test_zero_page_pdf_export(self, temp_dir: Path) -> None:
        """Test: PDF con zero pagine (edge case)."""
        pdf_path = temp_dir / "zero_pages.pdf"
        doc = fitz.open()
        doc.save(pdf_path)
        doc.close()

        output_dir = temp_dir / "images"

        handles_before = count_open_file_handles()

        result = export_pages_as_images(pdf_path, output_dir)

        handles_after = count_open_file_handles()

        assert result == []

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before

    def test_large_pdf_simulation_closes_documents(self, temp_dir: Path) -> None:
        """Test: Simulazione PDF grande (molte pagine) chiude doc."""
        pdf_path = temp_dir / "large.pdf"
        doc = fitz.open()

        # Crea 10 pagine
        for i in range(10):
            page = doc.new_page()
            page.insert_text((50, 50), f"Page {i + 1}" * 100, fontsize=8)

        doc.save(pdf_path)
        doc.close()

        output_dir = temp_dir / "images"
        config = ExportImagesConfig(dpi=72)  # Bassa risoluzione per simulazione

        handles_before = count_open_file_handles()

        result = export_pages_as_images(pdf_path, output_dir, config=config)

        handles_after = count_open_file_handles()

        assert len(result) == 10

        if PSUTIL_AVAILABLE and handles_before >= 0 and handles_after >= 0:
            assert handles_after <= handles_before + 1

    def test_multiple_sequential_operations_no_leak(
        self, valid_pdf: Path, temp_dir: Path
    ) -> None:
        """Test: Operazioni sequenziali multiple non accumulano leak."""
        handles_baseline = count_open_file_handles()

        for i in range(3):
            # Compress
            compress_out = temp_dir / f"compressed_{i}.pdf"
            compress(valid_pdf, compress_out)

            # Export
            export_dir = temp_dir / f"images_{i}"
            export_pages_as_images(valid_pdf, export_dir)

            # Headers/Footers
            hf_out = temp_dir / f"with_hf_{i}.pdf"
            config = HeaderFooterConfig(
                header=HeaderFooterSection(center=f"Iteration {i}")
            )
            add_headers_footers(valid_pdf, hf_out, config)

        handles_final = count_open_file_handles()

        # Dopo 3 iterazioni, non dovrebbero accumularsi handle aperti
        if PSUTIL_AVAILABLE and handles_baseline >= 0 and handles_final >= 0:
            # Permettiamo un leeway piccolo per OS temporaries
            assert handles_final <= handles_baseline + 3, \
                f"Leak accumulation: {handles_baseline} → {handles_final}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
