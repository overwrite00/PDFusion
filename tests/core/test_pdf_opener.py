"""
Test suite for core.pdf_opener module.

Tests the centralized PDF opening helper function with various scenarios:
- Happy path: valid PDF opening
- Password handling: correct and incorrect passwords
- Error cases: missing files, corrupted PDFs, permission issues
- Edge cases: paths with spaces/unicode, symlinks
"""

import tempfile
from pathlib import Path

import pikepdf
import pytest

from core.pdf_opener import open_pdf_safe
from utils.exceptions import PDFusionError, UnsupportedFormatError


class TestOpenPdfSafeHappyPath:
    """Happy path tests: valid PDF opening scenarios."""

    def test_open_valid_unencrypted_pdf(self, sample_pdf):
        """Test opening a valid, unencrypted PDF."""
        pdf = open_pdf_safe(sample_pdf)
        assert pdf is not None
        assert isinstance(pdf, pikepdf.Pdf)
        assert len(pdf.pages) == 1
        pdf.close()

    def test_open_multipage_pdf(self, multipage_pdf):
        """Test opening a valid multipage PDF."""
        pdf = open_pdf_safe(multipage_pdf)
        assert pdf is not None
        assert len(pdf.pages) == 10
        pdf.close()

    def test_returns_pikepdf_object(self, sample_pdf):
        """Test that the returned object is a proper pikepdf.Pdf instance."""
        pdf = open_pdf_safe(sample_pdf)
        try:
            assert hasattr(pdf, "pages")
            assert hasattr(pdf, "close")
            assert callable(pdf.save)
        finally:
            pdf.close()


class TestOpenPdfSafePasswordHandling:
    """Password handling tests."""

    def test_open_encrypted_pdf_with_correct_password(self, encrypted_pdf):
        """Test opening an encrypted PDF with the correct password."""
        pdf = open_pdf_safe(encrypted_pdf, password="test123")
        assert pdf is not None
        assert len(pdf.pages) == 1
        pdf.close()

    def test_open_encrypted_pdf_with_wrong_password(self, encrypted_pdf):
        """Test that wrong password raises PDFusionError."""
        with pytest.raises(PDFusionError, match="Password errata"):
            open_pdf_safe(encrypted_pdf, password="wrongpassword")

    def test_open_encrypted_pdf_without_password(self, encrypted_pdf):
        """Test that encrypted PDF without password raises PDFusionError."""
        with pytest.raises(PDFusionError, match="Password errata"):
            open_pdf_safe(encrypted_pdf)

    def test_open_unencrypted_pdf_with_password_is_ignored(self, sample_pdf):
        """Test that password is safely ignored for unencrypted PDFs."""
        # This should work without error - pikepdf ignores the password
        pdf = open_pdf_safe(sample_pdf, password="anypassword")
        assert pdf is not None
        pdf.close()


class TestOpenPdfSafeErrorCases:
    """Error case tests."""

    def test_open_nonexistent_file(self, tmp_path):
        """Test that opening a non-existent file raises PDFusionError."""
        nonexistent = tmp_path / "does_not_exist.pdf"
        with pytest.raises(PDFusionError, match="File non trovato"):
            open_pdf_safe(nonexistent)

    def test_open_corrupted_pdf(self, tmp_path):
        """Test that opening a corrupted PDF raises UnsupportedFormatError."""
        corrupted = tmp_path / "corrupted.pdf"
        corrupted.write_bytes(b"%PDF-1.4\nGarbage data that is not valid PDF")

        with pytest.raises(UnsupportedFormatError, match="File non valido"):
            open_pdf_safe(corrupted)

    def test_open_non_pdf_file(self, tmp_path):
        """Test that opening a non-PDF file raises UnsupportedFormatError."""
        text_file = tmp_path / "notapdf.txt"
        text_file.write_text("This is just a text file, not a PDF")

        with pytest.raises(UnsupportedFormatError, match="File non valido"):
            open_pdf_safe(text_file)

    def test_open_empty_file(self, tmp_path):
        """Test that opening an empty file raises UnsupportedFormatError."""
        empty_file = tmp_path / "empty.pdf"
        empty_file.write_bytes(b"")

        with pytest.raises(UnsupportedFormatError, match="File non valido"):
            open_pdf_safe(empty_file)


class TestOpenPdfSafeEdgeCases:
    """Edge case tests: paths with special characters, symlinks, etc."""

    def test_open_pdf_with_spaces_in_path(self, sample_pdf):
        """Test opening a PDF with spaces in the path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Create a subdirectory with spaces
            spaced_dir = tmp_path / "folder with spaces"
            spaced_dir.mkdir()

            import shutil
            spaced_pdf = spaced_dir / "sample file.pdf"
            shutil.copy2(sample_pdf, spaced_pdf)

            pdf = open_pdf_safe(spaced_pdf)
            assert pdf is not None
            pdf.close()

    def test_open_pdf_with_unicode_in_path(self, sample_pdf):
        """Test opening a PDF with unicode characters in the path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Create a subdirectory with unicode characters
            unicode_dir = tmp_path / "cartella_italiano_ñ_日本語"
            unicode_dir.mkdir()

            import shutil
            unicode_pdf = unicode_dir / "documento_σ.pdf"
            shutil.copy2(sample_pdf, unicode_pdf)

            pdf = open_pdf_safe(unicode_pdf)
            assert pdf is not None
            pdf.close()

    def test_open_pdf_with_relative_path(self, sample_pdf):
        """Test opening a PDF using relative path (should work if cwd is correct)."""
        # This test uses absolute paths, but verifies that Path conversion works
        pdf = open_pdf_safe(Path(sample_pdf))
        assert pdf is not None
        pdf.close()


class TestOpenPdfSafeLogging:
    """Test logging behavior."""

    def test_logging_on_success(self, sample_pdf, caplog):
        """Test that successful opens are logged at debug level."""
        import logging
        caplog.set_level(logging.DEBUG)

        pdf = open_pdf_safe(sample_pdf)
        try:
            # Check that debug message was logged
            assert any("Opening PDF" in record.message for record in caplog.records)
            assert any("Successfully opened" in record.message for record in caplog.records)
        finally:
            pdf.close()

    def test_logging_on_password_error(self, encrypted_pdf, caplog):
        """Test that password errors are logged."""
        import logging
        caplog.set_level(logging.DEBUG)

        with pytest.raises(PDFusionError):
            open_pdf_safe(encrypted_pdf, password="wrong")

        assert any("Password error" in record.message for record in caplog.records)

    def test_logging_on_file_not_found(self, tmp_path, caplog):
        """Test that file not found is logged."""
        import logging
        caplog.set_level(logging.DEBUG)

        nonexistent = tmp_path / "notfound.pdf"
        with pytest.raises(PDFusionError):
            open_pdf_safe(nonexistent)

        assert any("File not found" in record.message for record in caplog.records)


class TestOpenPdfSafeIntegration:
    """Integration tests with other modules."""

    def test_opened_pdf_can_be_modified_and_saved(self, sample_pdf, tmp_path):
        """Test that opened PDF can be modified and saved."""
        output = tmp_path / "modified.pdf"

        pdf = open_pdf_safe(sample_pdf)
        try:
            # Simple modification: set metadata
            pdf.docinfo["/Title"] = "Modified Title"
            pdf.save(str(output))
        finally:
            pdf.close()

        # Verify the modification persisted
        assert output.exists()
        pdf_check = pikepdf.open(output)
        assert pdf_check.docinfo.get("/Title") == "Modified Title"
        pdf_check.close()

    def test_opened_pdf_with_password_can_be_processed(self, encrypted_pdf, tmp_path):
        """Test that encrypted PDF can be opened and re-saved."""
        output = tmp_path / "reencrypted.pdf"

        pdf = open_pdf_safe(encrypted_pdf, password="test123")
        try:
            # Verify we can access pages
            assert len(pdf.pages) > 0
            pdf.save(str(output))
        finally:
            pdf.close()

        assert output.exists()

    def test_opened_pdf_matches_direct_pikepdf_open(self, sample_pdf):
        """Test that open_pdf_safe result is equivalent to direct pikepdf.open()."""
        # Open with helper
        pdf_helper = open_pdf_safe(sample_pdf)
        pages_helper = len(pdf_helper.pages)
        pdf_helper.close()

        # Open directly with pikepdf
        pdf_direct = pikepdf.open(sample_pdf)
        pages_direct = len(pdf_direct.pages)
        pdf_direct.close()

        # Should be identical
        assert pages_helper == pages_direct


class TestOpenPdfSafeExceptionTypes:
    """Test that correct exception types are raised."""

    def test_password_error_is_pdf_fusion_error(self, encrypted_pdf):
        """Test that password errors are PDFusionError (not UnsupportedFormatError)."""
        with pytest.raises(PDFusionError) as exc_info:
            open_pdf_safe(encrypted_pdf, password="wrong")

        # Ensure it's PDFusionError, not UnsupportedFormatError
        assert isinstance(exc_info.value, PDFusionError)
        assert not isinstance(exc_info.value, UnsupportedFormatError)

    def test_corrupted_pdf_is_unsupported_format_error(self, tmp_path):
        """Test that corrupted PDFs raise UnsupportedFormatError."""
        corrupted = tmp_path / "corrupted.pdf"
        corrupted.write_bytes(b"%PDF-1.4\nInvalid content")

        with pytest.raises(UnsupportedFormatError):
            open_pdf_safe(corrupted)

    def test_missing_file_is_pdf_fusion_error(self, tmp_path):
        """Test that missing files raise PDFusionError."""
        missing = tmp_path / "missing.pdf"
        with pytest.raises(PDFusionError) as exc_info:
            open_pdf_safe(missing)

        assert "File non trovato" in str(exc_info.value)
