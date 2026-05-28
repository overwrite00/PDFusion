"""
Test completo per batch operations con password per-file.

Covers:
- Happy path: file non-protetti
- Happy path: file protetti con SAME password
- Happy path: file protetti con DIFFERENT passwords
- Error case: file protetto, no password (silent failure prevention)
- Error case: password errata per file
- Error case: mixed protected/unprotected files
- Stress test: batch con 10 file e 10 password diverse
- Backwards compatibility: password_map=None fallback
"""

import shutil
from pathlib import Path

import pytest

from core.batch import BatchJob, BatchOperation, run_batch
from core.compress import CompressConfig, CompressPreset
from core.protect import ProtectConfig
from utils.exceptions import PDFusionError


@pytest.fixture
def three_unprotected_pdfs(sample_pdf, tmp_path):
    """Crea 3 PDF non-protetti per il batch."""
    src_dir = tmp_path / "src_unprotected"
    src_dir.mkdir()
    paths = []
    for i in range(3):
        dst = src_dir / f"input_{i}.pdf"
        shutil.copy(sample_pdf, dst)
        paths.append(dst)
    return paths


@pytest.fixture
def three_protected_same_pwd(sample_pdf, tmp_path):
    """Crea 3 PDF protetti con STESSA password."""
    from core.protect import protect

    src_dir = tmp_path / "src_protected_same"
    src_dir.mkdir()
    temp_dir = tmp_path / "temp_protected_same"
    temp_dir.mkdir()

    paths = []
    for i in range(3):
        # Proteggi il PDF con password "same123" nella config (output password)
        dst = src_dir / f"input_{i}.pdf"
        temp_protected = temp_dir / f"protected_{i}.pdf"
        protect(
            sample_pdf,
            temp_protected,
            ProtectConfig(user_password="same123"),  # Set OUTPUT password
        )
        shutil.move(temp_protected, dst)
        paths.append(dst)
    return paths


@pytest.fixture
def three_protected_diff_pwd(sample_pdf, tmp_path):
    """Crea 3 PDF protetti con PASSWORD DIVERSE."""
    from core.protect import protect

    src_dir = tmp_path / "src_protected_diff"
    src_dir.mkdir()
    temp_dir = tmp_path / "temp_protected_diff"
    temp_dir.mkdir()

    paths = []
    passwords = ["pwd_alpha", "pwd_beta", "pwd_gamma"]
    for i, pwd in enumerate(passwords):
        # Proteggi il PDF con password diversa nella config (output password)
        dst = src_dir / f"input_{i}.pdf"
        temp_protected = temp_dir / f"protected_{i}.pdf"
        protect(
            sample_pdf,
            temp_protected,
            ProtectConfig(user_password=pwd),  # Set OUTPUT password
        )
        shutil.move(temp_protected, dst)
        paths.append(dst)
    return paths, passwords


@pytest.fixture
def mixed_protected_unprotected(sample_pdf, tmp_path):
    """Crea 3 PDF: 2 protetti (password diverse), 1 no."""
    from core.protect import protect

    src_dir = tmp_path / "src_mixed"
    src_dir.mkdir()
    temp_dir = tmp_path / "temp_mixed"
    temp_dir.mkdir()

    # File 0: protetto con pwd1
    dst0 = src_dir / "input_0.pdf"
    temp_protected0 = temp_dir / "protected_0.pdf"
    protect(
        sample_pdf,
        temp_protected0,
        ProtectConfig(user_password="pwd1"),  # Set OUTPUT password
    )
    shutil.move(temp_protected0, dst0)

    # File 1: NON protetto
    dst1 = src_dir / "input_1.pdf"
    shutil.copy(sample_pdf, dst1)

    # File 2: protetto con pwd2
    dst2 = src_dir / "input_2.pdf"
    temp_protected2 = temp_dir / "protected_2.pdf"
    protect(
        sample_pdf,
        temp_protected2,
        ProtectConfig(user_password="pwd2"),  # Set OUTPUT password
    )
    shutil.move(temp_protected2, dst2)

    return [dst0, dst1, dst2], {"dst0": "pwd1", "dst2": "pwd2"}


class TestBatchPasswordsHappyPath:
    """Happy path tests."""

    def test_unprotected_files_no_password(self, three_unprotected_pdfs, tmp_dir):
        """Happy path 1: batch di file non-protetti."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
        )
        results = run_batch(three_unprotected_pdfs, job)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.output_path.exists() for r in results)

    def test_protected_files_same_password(self, three_protected_same_pwd, tmp_dir):
        """Happy path 2: batch di file protetti con SAME password."""
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password_map={path: "same123" for path in three_protected_same_pwd},
        )
        results = run_batch(three_protected_same_pwd, job)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.output_path.exists() for r in results)

    def test_protected_files_different_passwords(
        self, three_protected_diff_pwd, tmp_dir
    ):
        """Happy path 3: batch di file protetti con DIFFERENT passwords."""
        paths, passwords = three_protected_diff_pwd
        # Crea password_map per i file con password diverse
        password_map = {path: pwd for path, pwd in zip(paths, passwords, strict=True)}

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password_map=password_map,
        )
        results = run_batch(paths, job)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.output_path.exists() for r in results)

    def test_mixed_protected_unprotected(self, mixed_protected_unprotected, tmp_dir):
        """Happy path 4: batch di file mixed protected/unprotected."""
        paths, pwd_map = mixed_protected_unprotected
        # Crea password_map solo per i file protetti
        password_map = {paths[0]: pwd_map["dst0"], paths[2]: pwd_map["dst2"]}

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password_map=password_map,
        )
        results = run_batch(paths, job)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.output_path.exists() for r in results)


class TestBatchPasswordsErrorCases:
    """Error case tests - verify explicit error messages, not silent failures."""

    def test_protected_file_no_password_fails_explicitly(
        self, three_protected_same_pwd, tmp_dir
    ):
        """Error case 1: file protetto, no password provided (must raise, not silent)."""
        # Password_map ASSENTE per i file protetti
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password_map={},  # Vuoto!
        )
        results = run_batch(three_protected_same_pwd, job)
        # Tutti i file devono fallire con errore, NON silent
        failures = [r for r in results if not r.success]
        assert len(failures) == 3
        # Verifica che l'errore sia esplicito
        for r in failures:
            assert r.error is not None
            assert len(r.error) > 0
            # L'errore deve menzionare password/encryption
            error_lower = r.error.lower()
            assert (
                "password" in error_lower
                or "encrypt" in error_lower
                or "pem" in error_lower
            )

    def test_wrong_password_fails_explicitly(
        self, three_protected_same_pwd, tmp_dir
    ):
        """Error case 2: wrong password per file (must raise, not silent)."""
        password_map = {path: "WRONG_PASSWORD" for path in three_protected_same_pwd}

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password_map=password_map,
        )
        results = run_batch(three_protected_same_pwd, job)
        failures = [r for r in results if not r.success]
        assert len(failures) == 3
        # Errori espliciti, non silent
        for r in failures:
            assert r.error is not None
            assert len(r.error) > 0


class TestBatchPasswordsStress:
    """Stress test: batch con 10 file e password diverse."""

    def test_ten_files_different_passwords(self, sample_pdf, tmp_path, tmp_dir):
        """Stress test: batch di 10 file con 10 diverse password."""
        from core.protect import protect

        src_dir = tmp_path / "src_stress"
        src_dir.mkdir()
        temp_dir = tmp_path / "temp_stress"
        temp_dir.mkdir()

        # Crea 10 file protetti con password diverse
        paths = []
        password_map = {}
        for i in range(10):
            pwd = f"stress_pwd_{i:02d}"
            dst = src_dir / f"input_{i:02d}.pdf"
            temp_protected = temp_dir / f"protected_{i:02d}.pdf"
            protect(
                sample_pdf,
                temp_protected,
                ProtectConfig(user_password=pwd),  # Set OUTPUT password
            )
            shutil.move(temp_protected, dst)
            paths.append(dst)
            password_map[dst] = pwd

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password_map=password_map,
        )
        results = run_batch(paths, job)
        assert len(results) == 10
        assert all(r.success for r in results)
        assert all(r.output_path.exists() for r in results)


class TestBatchPasswordsBackwardsCompat:
    """Backwards compatibility test: password_map=None fallback."""

    def test_password_map_none_fallback_to_job_password(
        self, three_protected_same_pwd, tmp_dir
    ):
        """
        Backwards compat: se password_map=None, usa job.password per tutti.
        Questo è il vecchio comportamento.
        """
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password="same123",  # Usa password comune
            password_map=None,  # Niente password_map
        )
        results = run_batch(three_protected_same_pwd, job)
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_password_map_empty_fallback_to_job_password(
        self, three_protected_same_pwd, tmp_dir
    ):
        """Backwards compat: se file non in password_map, usa job.password."""
        password_map = {}  # Vuoto
        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(preset=CompressPreset.EBOOK),
            password="same123",  # Fallback
            password_map=password_map,
        )
        results = run_batch(three_protected_same_pwd, job)
        assert len(results) == 3
        assert all(r.success for r in results)


class TestBatchPasswordsOperations:
    """Test password handling across different batch operations."""

    def test_protect_operation_with_password_map(
        self, three_protected_same_pwd, tmp_dir
    ):
        """Verifica che PROTECT operation usa password_map correttamente."""
        password_map = {path: "same123" for path in three_protected_same_pwd}

        job = BatchJob(
            operation=BatchOperation.PROTECT,
            output_dir=tmp_dir,
            operation_config=ProtectConfig(),
            password_map=password_map,
        )
        results = run_batch(three_protected_same_pwd, job)
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_watermark_operation_with_password_map(
        self, three_protected_diff_pwd, tmp_dir
    ):
        """Verifica che WATERMARK operation usa password_map correttamente."""
        paths, passwords = three_protected_diff_pwd
        password_map = {path: pwd for path, pwd in zip(paths, passwords, strict=True)}

        # Usa WatermarkConfig se disponibile
        job = BatchJob(
            operation=BatchOperation.WATERMARK,
            output_dir=tmp_dir,
            operation_config=None,  # Watermark senza config
            password_map=password_map,
        )
        results = run_batch(paths, job)
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_rotate_operation_with_password_map(
        self, three_protected_same_pwd, tmp_dir
    ):
        """Verifica che ROTATE operation usa password_map correttamente."""
        password_map = {path: "same123" for path in three_protected_same_pwd}

        job = BatchJob(
            operation=BatchOperation.ROTATE,
            output_dir=tmp_dir,
            operation_config=90,  # Rotazione 90 gradi
            password_map=password_map,
        )
        results = run_batch(three_protected_same_pwd, job)
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_merge_operation_with_password_map(
        self, three_protected_diff_pwd, tmp_dir
    ):
        """Verifica che MERGE_TO_ONE operation usa password_map correttamente."""
        paths, passwords = three_protected_diff_pwd
        password_map = {path: pwd for path, pwd in zip(paths, passwords, strict=True)}

        job = BatchJob(
            operation=BatchOperation.MERGE_TO_ONE,
            output_dir=tmp_dir,
            password_map=password_map,
        )
        results = run_batch(paths, job)
        assert len(results) == 1  # Merge returns one result
        assert results[0].success
        assert results[0].output_path.exists()

    def test_merge_operation_same_password(
        self, three_protected_same_pwd, tmp_dir
    ):
        """Verifica che MERGE_TO_ONE operation funziona con password_map uniformi."""
        password_map = {path: "same123" for path in three_protected_same_pwd}

        job = BatchJob(
            operation=BatchOperation.MERGE_TO_ONE,
            output_dir=tmp_dir,
            password_map=password_map,
        )
        results = run_batch(three_protected_same_pwd, job)
        assert len(results) == 1
        assert results[0].success
        assert results[0].output_path.exists()


class TestBatchPasswordsProgressCallback:
    """Test che progress callback funziona correttamente con password_map."""

    def test_progress_callback_with_password_map(
        self, three_protected_diff_pwd, tmp_dir
    ):
        """Verifica che progress callback riporta correttamente con password_map."""
        paths, passwords = three_protected_diff_pwd
        password_map = {path: pwd for path, pwd in zip(paths, passwords, strict=True)}

        progress = []

        def progress_cb(done, total, name):
            progress.append((done, total, name))

        job = BatchJob(
            operation=BatchOperation.COMPRESS,
            output_dir=tmp_dir,
            operation_config=CompressConfig(),
            password_map=password_map,
        )
        results = run_batch(paths, job, progress_callback=progress_cb)
        assert len(progress) == 3
        assert progress[-1][:2] == (3, 3)
        assert all(r.success for r in results)
