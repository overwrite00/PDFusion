import pytest
import pikepdf
from core.metadata import read_metadata, write_metadata


class TestReadMetadata:
    def test_returns_dict(self, sample_pdf):
        meta = read_metadata(sample_pdf)
        assert isinstance(meta, dict)

    def test_known_keys(self, sample_pdf):
        meta = read_metadata(sample_pdf)
        for key in ("title", "author", "subject", "creator", "producer", "keywords"):
            assert key in meta


class TestWriteMetadata:
    def test_write_and_read_back(self, sample_pdf, tmp_output):
        result = write_metadata(
            sample_pdf,
            tmp_output,
            title="Test Title",
            author="Test Author",
            subject="Test Subject",
        )
        meta = read_metadata(result)
        assert meta["title"] == "Test Title"
        assert meta["author"] == "Test Author"
        assert meta["subject"] == "Test Subject"

    def test_partial_write(self, sample_pdf, tmp_output):
        result = write_metadata(sample_pdf, tmp_output, title="Only Title")
        meta = read_metadata(result)
        assert meta["title"] == "Only Title"

    def test_clear_field(self, sample_pdf, tmp_output):
        result = write_metadata(sample_pdf, tmp_output, title="")
        meta = read_metadata(result)
        assert meta["title"] == ""
