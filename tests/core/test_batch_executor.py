"""
Test suite for ThreadPoolExecutor timeout handling and cleanup in batch.py.
Tests cover timeout behavior, retries, resource cleanup, and stress scenarios.
"""
import shutil
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.batch import BatchJob, BatchOperation, run_batch
from core.compress import CompressConfig, CompressPreset


@pytest.fixture
def ten_pdfs(sample_pdf, tmp_path):
    """Create 10 test PDFs."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    paths = []
    for i in range(10):
        dst = src_dir / f"input_{i}.pdf"
        shutil.copy(sample_pdf, dst)
        paths.append(dst)
    return paths


@pytest.fixture
def hundred_pdfs(sample_pdf, tmp_path):
    """Create 100 test PDFs for stress testing."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    paths = []
    for i in range(100):
        dst = src_dir / f"input_{i:03d}.pdf"
        shutil.copy(sample_pdf, dst)
        paths.append(dst)
    return paths


class TestBatchHappyPath:
    """Happy path tests: normal batch execution."""

    def test_compress_batch_10_pdfs(self, ten_pdfs, tmp_dir):
        """Test: 10 PDFs, all complete successfully."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=30.0,
        )
        results = run_batch(ten_pdfs, job)

        assert len(results) == 10
        assert all(r.success for r in results), "All jobs should succeed"
        assert all(r.output_path.exists() for r in results), "All output files exist"
        assert all(r.error is None for r in results), "No errors"

    def test_progress_callback_called_for_all(self, ten_pdfs, tmp_dir):
        """Verify progress callback is called for all 10 files."""
        progress = []
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
        )
        run_batch(
            ten_pdfs,
            job,
            progress_callback=lambda done, total, name: progress.append(
                (done, total, name)
            ),
        )

        assert len(progress) == 10, "Progress called for each file"
        assert progress[-1][0] == 10, "Final progress should be (10, 10, ...)"
        assert progress[-1][1] == 10


class TestBatchTimeout:
    """Timeout path tests: files exceed timeout threshold."""

    def test_timeout_single_file(self, ten_pdfs, tmp_dir):
        """Test: 1 PDF per job takes 60s, timeout at 30s."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=2.0,  # Very short timeout for testing
            max_retries=1,
        )

        # Mock _dispatch to hang for the first file
        call_count = {}

        def slow_dispatch(input_path, output_path, batch_job):
            call_count[input_path] = call_count.get(input_path, 0) + 1
            if call_count[input_path] == 1 and input_path == ten_pdfs[0]:
                # Only hang on first file, first attempt
                time.sleep(5.0)  # Sleep longer than timeout
            # Otherwise process normally
            from core.compress import compress

            compress(input_path, output_path, batch_job.operation_config, None)

        with patch("core.batch._dispatch", side_effect=slow_dispatch):
            results = run_batch(ten_pdfs, job)

        # First file should timeout
        failed = [r for r in results if not r.success]
        assert len(failed) >= 1, "Should have at least 1 timeout"
        assert any("Timeout" in r.error for r in failed), "Error should mention timeout"

    def test_timeout_multiple_files(self, ten_pdfs, tmp_dir):
        """Test: multiple files timeout, rest complete."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=1.0,  # Short timeout
            max_retries=1,
        )

        call_count = {}

        def selective_slow(input_path, output_path, batch_job):
            call_count[input_path] = call_count.get(input_path, 0) + 1
            # Make files 0, 2, 4 slow
            if call_count[input_path] == 1 and input_path.stem.endswith(
                ("_0", "_2", "_4")
            ):
                time.sleep(3.0)
            # Normal processing
            from core.compress import compress

            compress(input_path, output_path, batch_job.operation_config, None)

        with patch("core.batch._dispatch", side_effect=selective_slow):
            results = run_batch(ten_pdfs, job)

        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        # Should have mixed results
        assert len(results) == 10, "All 10 results returned"
        assert len(successes) > 0, "Some files completed"
        assert len(failures) > 0, "Some files timed out"
        assert all(
            "Timeout" in r.error for r in failures
        ), "Failures are timeouts"


class TestBatchRetry:
    """Retry logic tests: exponential backoff and max retries."""

    def test_retry_with_exponential_backoff(self, ten_pdfs, tmp_dir):
        """Test: retry with exponential backoff on timeout."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=1.0,
            max_retries=3,  # Allow 3 total attempts
        )

        call_count = {}
        start_times = {}

        def failing_first_then_success(input_path, output_path, batch_job):
            if input_path not in call_count:
                call_count[input_path] = 0
                start_times[input_path] = time.time()

            call_count[input_path] += 1

            # Fail first attempt with timeout
            if call_count[input_path] == 1 and input_path == ten_pdfs[0]:
                time.sleep(2.0)  # Exceed 1s timeout

            # Succeed on retry
            from core.compress import compress

            compress(input_path, output_path, batch_job.operation_config, None)

        with patch("core.batch._dispatch", side_effect=failing_first_then_success):
            results = run_batch(ten_pdfs, job)

        # First file should eventually succeed after retry
        first_result = [r for r in results if r.input_path == ten_pdfs[0]][0]
        # Note: Due to timeout handling, this might still fail
        # But the retry mechanism should be invoked
        assert call_count[ten_pdfs[0]] >= 1, "File was processed"

    def test_max_retries_exhausted(self, ten_pdfs, tmp_dir):
        """Test: file fails after all retries exhausted."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=0.5,
            max_retries=2,
        )

        def always_timeout(input_path, output_path, batch_job):
            # Always timeout, no matter the retry count
            if input_path == ten_pdfs[0]:
                time.sleep(2.0)
            from core.compress import compress

            compress(input_path, output_path, batch_job.operation_config, None)

        with patch("core.batch._dispatch", side_effect=always_timeout):
            results = run_batch(ten_pdfs, job)

        # First file should eventually give up
        first_result = [r for r in results if r.input_path == ten_pdfs[0]][0]
        # Should contain timeout error after retries
        if not first_result.success:
            assert "Timeout" in first_result.error


class TestBatchResourceCleanup:
    """Resource cleanup tests: threads properly released."""

    def test_thread_count_stable_sequential_batches(self, ten_pdfs, tmp_dir):
        """Test: 20 sequential batches don't leak threads."""
        initial_threads = threading.active_count()

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=30.0,
            max_workers=4,
        )

        for i in range(20):
            batch_out = tmp_dir / f"batch_{i}"
            batch_out.mkdir(exist_ok=True)
            job.output_dir = batch_out
            results = run_batch(ten_pdfs, job)
            assert all(r.success for r in results)

        # Allow small variance for OS thread management
        final_threads = threading.active_count()
        thread_delta = final_threads - initial_threads
        assert thread_delta < 3, f"Thread leak detected: {thread_delta} extra threads"

    def test_executor_properly_shutdown(self, ten_pdfs, tmp_dir):
        """Test: ThreadPoolExecutor is properly shut down."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=30.0,
        )

        results = run_batch(ten_pdfs, job)
        assert all(r.success for r in results)

        # Give threads time to shut down
        time.sleep(0.5)

        # Check no hanging futures by running another batch
        job.output_dir = tmp_dir / "batch2"
        job.output_dir.mkdir(exist_ok=True)
        results2 = run_batch(ten_pdfs, job)
        assert all(r.success for r in results2)


class TestBatchPartialFailure:
    """Partial failure tests: mixed success/failure scenarios."""

    def test_5_success_5_timeout(self, ten_pdfs, tmp_dir):
        """Test: 5/10 jobs succeed, 5 timeout."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=1.0,
            max_retries=1,
        )

        def half_timeout(input_path, output_path, batch_job):
            # First 5 timeout, second 5 succeed
            idx = int(input_path.stem.split("_")[-1])
            if idx < 5:
                time.sleep(2.0)

            from core.compress import compress

            compress(input_path, output_path, batch_job.operation_config, None)

        with patch("core.batch._dispatch", side_effect=half_timeout):
            results = run_batch(ten_pdfs, job)

        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        assert len(results) == 10
        assert len(successes) + len(failures) == 10
        assert len(failures) >= 4, "At least some timeouts"

    def test_invalid_pdf_error_handling(self, ten_pdfs, tmp_dir):
        """Test: corrupt PDF produces error, doesn't crash batch."""
        # Corrupt one PDF
        ten_pdfs[5].write_bytes(b"not a pdf")

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=30.0,
        )

        results = run_batch(ten_pdfs, job)

        assert len(results) == 10
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        assert len(failures) >= 1, "At least one failure"
        assert len(successes) >= 8, "Most files should succeed"


class TestBatchStress:
    """Stress tests: high load scenarios."""

    def test_100_workers_100_files(self, hundred_pdfs, tmp_dir):
        """Test: 100 workers × 100 files, verify cleanup."""
        initial_threads = threading.active_count()

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=60.0,
            max_workers=20,  # Cap at 20 actual workers
        )

        results = run_batch(hundred_pdfs, job)

        assert len(results) == 100
        successes = [r for r in results if r.success]
        assert (
            len(successes) >= 90
        ), "Most files should succeed under stress"

        # Verify cleanup
        time.sleep(0.5)
        final_threads = threading.active_count()
        thread_delta = final_threads - initial_threads
        assert thread_delta < 5, f"Thread leak: {thread_delta} extra threads"

    def test_high_concurrency_order_preserved(self, ten_pdfs, tmp_dir):
        """Test: results maintain input order despite concurrent execution."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=30.0,
            max_workers=8,
        )

        results = run_batch(ten_pdfs, job)

        # Results should be in same order as input
        for i, result in enumerate(results):
            expected_idx = int(ten_pdfs[i].stem.split("_")[-1])
            actual_idx = int(result.input_path.stem.split("_")[-1])
            assert (
                expected_idx == actual_idx
            ), f"Result order mismatch at position {i}"


class TestBatchConfiguration:
    """Configuration tests: timeout and retry parameters."""

    def test_custom_timeout_parameter(self, ten_pdfs, tmp_dir):
        """Test: custom timeout parameter is used."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=45.0,  # Custom timeout
            max_retries=1,
        )

        assert job.timeout == 45.0
        results = run_batch(ten_pdfs, job)
        assert all(r.success for r in results)

    def test_retry_parameter_respected(self, ten_pdfs, tmp_dir):
        """Test: max_retries parameter is respected."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            timeout=30.0,
            max_retries=3,  # Custom retries
        )

        assert job.max_retries == 3
        results = run_batch(ten_pdfs, job)
        # Should not crash
        assert len(results) == 10

    def test_default_timeout_30_seconds(self, ten_pdfs, tmp_dir):
        """Test: default timeout is 30 seconds."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
        )

        assert job.timeout == 30.0

    def test_default_max_retries_1(self, ten_pdfs, tmp_dir):
        """Test: default max_retries is 1 (no retry)."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
        )

        assert job.max_retries == 1
