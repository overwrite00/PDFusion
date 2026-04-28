from core.metadata import PDFMetadata, read_metadata, write_metadata


class TestReadMetadata:
    def test_returns_dict(self, sample_pdf):
        meta = read_metadata(sample_pdf)
        assert isinstance(meta, PDFMetadata)

    def test_known_keys(self, sample_pdf):
        meta = read_metadata(sample_pdf)
        # PDFMetadata è un dataclass con questi attributi
        for attr in ("title", "author", "subject", "creator", "producer", "keywords"):
            assert hasattr(meta, attr)


class TestWriteMetadata:
    def test_write_and_read_back(self, sample_pdf, tmp_output):
        result = write_metadata(
            sample_pdf,
            PDFMetadata(title="Test Title", author="Test Author", subject="Test Subject"),
            tmp_output,
        )
        meta = read_metadata(result)
        assert meta.title == "Test Title"
        assert meta.author == "Test Author"
        assert meta.subject == "Test Subject"

    def test_partial_write(self, sample_pdf, tmp_output):
        result = write_metadata(sample_pdf, PDFMetadata(title="Only Title"), tmp_output)
        meta = read_metadata(result)
        assert meta.title == "Only Title"

    def test_clear_field(self, sample_pdf, tmp_output):
        result = write_metadata(sample_pdf, PDFMetadata(title=""), tmp_output)
        meta = read_metadata(result)
        assert meta.title is None  # campo cancellato → None
