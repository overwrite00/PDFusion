import pytest
import shutil
from pathlib import Path
from core.batch import run_batch, BatchOperation, BatchJob, BatchResult
from core.compress import CompressConfig, CompressPreset


@pytest.fixture
def three_pdfs(sample_pdf, tmp_path):
    paths = []
    for i in range(3):
        dst = tmp_path / f"input_{i}.pdf"
        shutil.copy(sample_pdf, dst)
        paths.append(dst)
    return paths


class TestRunBatch:
    def test_compress_batch(self, three_pdfs, tmp_dir):
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
        )
        results = run_batch(three_pdfs, job)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.output_path.exists() for r in results)

    def test_rotate_batch(self, three_pdfs, tmp_dir):
        job = BatchJob(
            operation=BatchOperation.ROTATE,
            output_dir=tmp_dir,
            operation_config=90,  # angolo intero
        )
        results = run_batch(three_pdfs, job)
        assert all(r.success for r in results)

    def test_progress_callback(self, three_pdfs, tmp_dir):
        progress = []
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(),
        )
        run_batch(
            three_pdfs, job,
            progress_callback=lambda done, total, name: progress.append((done, total)),
        )
        assert len(progress) == 3
        assert progress[-1] == (3, 3)

    def test_empty_input_returns_empty(self, tmp_dir):
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(),
        )
        results = run_batch([], job)
        assert results == []

    def test_partial_failure(self, three_pdfs, tmp_dir):
        # Sovrascrive uno dei file con contenuto non-PDF
        three_pdfs[1].write_bytes(b"not a pdf file content")
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(),
        )
        results = run_batch(three_pdfs, job)
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(failures) >= 1
        assert len(successes) >= 1
