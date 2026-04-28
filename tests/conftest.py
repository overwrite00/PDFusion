"""
Fixtures pytest condivise tra tutti i test.
I PDF vengono generati on-demand se non esistono già.
"""
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES_DIR / "sample.pdf"
MULTIPAGE = FIXTURES_DIR / "multipage.pdf"
ENCRYPTED = FIXTURES_DIR / "encrypted.pdf"
WITH_IMAGES = FIXTURES_DIR / "with_images.pdf"


def _ensure_fixtures() -> None:
    if not SAMPLE.exists() or not MULTIPAGE.exists():
        subprocess.run(
            [sys.executable, str(FIXTURES_DIR / "create_fixtures.py")],
            check=True,
        )


@pytest.fixture(scope="session", autouse=True)
def generate_fixtures():
    _ensure_fixtures()


@pytest.fixture(scope="session")
def sample_pdf() -> Path:
    return SAMPLE


@pytest.fixture(scope="session")
def multipage_pdf() -> Path:
    return MULTIPAGE


@pytest.fixture(scope="session")
def encrypted_pdf() -> Path:
    return ENCRYPTED


@pytest.fixture(scope="session")
def with_images_pdf() -> Path:
    return WITH_IMAGES


@pytest.fixture
def tmp_output(tmp_path) -> Path:
    return tmp_path / "output.pdf"


@pytest.fixture
def tmp_dir(tmp_path) -> Path:
    return tmp_path
