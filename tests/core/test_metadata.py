import warnings

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

    def test_author_write_does_not_warn_xmp_type(self, sample_pdf, tmp_output):
        """Regression: dc:creator is an XMP ordered array (rdf:Seq), not a
        plain string. pikepdf >= 10.13 emits XmpTypeWarning if assigned a str
        directly. docinfo /Author (what read_metadata/author actually reads)
        must still round-trip correctly as a plain string.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = write_metadata(
                sample_pdf, PDFMetadata(author="Test Author"), tmp_output
            )
        meta = read_metadata(result)
        assert meta.author == "Test Author"

    def test_partial_write(self, sample_pdf, tmp_output):
        result = write_metadata(sample_pdf, PDFMetadata(title="Only Title"), tmp_output)
        meta = read_metadata(result)
        assert meta.title == "Only Title"

    def test_clear_field(self, sample_pdf, tmp_output):
        result = write_metadata(sample_pdf, PDFMetadata(title=""), tmp_output)
        meta = read_metadata(result)
        assert meta.title is None  # campo cancellato → None
