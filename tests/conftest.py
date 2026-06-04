"""
Fixtures pytest condivise tra tutti i test.
I PDF vengono generati on-demand se non esistono già.
"""
import gc
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox

# ---------------------------------------------------------------------------
# Qt headless setup (CRITICAL — must run before any PyQt6 import)
# ---------------------------------------------------------------------------
# On headless CI runners (Linux GitHub Actions), instantiating a QApplication
# against the xcb/X11 platform plugin crashes with "Fatal Python error: Aborted"
# (SIGABRT, exit code 134) even when xvfb is running. The robust, officially
# supported solution is Qt's "offscreen" platform plugin, which renders to an
# in-memory buffer and requires no display server. This lets every Qt test run
# normally (no skips) on Windows, Linux and macOS alike.
#
# We force "offscreen" when no usable display is configured OR when running on
# a CI runner. The latter is essential: GitHub Actions' xvfb sets DISPLAY, but
# the xcb plugin still aborts there — so the presence of DISPLAY is NOT a
# reliable signal that xcb will work. On a developer's machine with a real
# display (and not under CI) we keep the native platform. Setting this here, at
# conftest import time before any test module imports PyQt6, guarantees the
# variable is in place when Qt initializes.
if not os.environ.get("QT_QPA_PLATFORM"):
    _on_ci = any(
        os.environ.get(marker)
        for marker in ("CI", "GITHUB_ACTIONS", "CONTINUOUS_INTEGRATION")
    )
    _is_native_desktop = os.name == "nt" or sys.platform == "darwin"
    _has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    # Use the native platform only on a real desktop that is not a CI runner.
    _use_native = _is_native_desktop or (_has_display and not _on_ci)
    if not _use_native:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES_DIR / "sample.pdf"
MULTIPAGE = FIXTURES_DIR / "multipage.pdf"
ENCRYPTED = FIXTURES_DIR / "encrypted.pdf"
WITH_IMAGES = FIXTURES_DIR / "with_images.pdf"


def is_headless_environment() -> bool:
    """
    Reports whether a QApplication CANNOT be initialized in this environment.

    With Qt's "offscreen" platform plugin forced above for displayless
    environments, a QApplication can always be created safely — there is no
    longer any need to skip Qt tests on CI. This always returns ``False`` so
    that all Qt tests actually run (on Windows, Linux headless and macOS).

    The function is retained for backward compatibility with existing test
    fixtures that import it.
    """
    return False


def _ensure_fixtures() -> None:
    if not SAMPLE.exists() or not MULTIPAGE.exists():
        subprocess.run(
            [sys.executable, str(FIXTURES_DIR / "create_fixtures.py")],
            check=True,
        )


def _create_minimal_ttf_file() -> Path:
    """
    Crea un file TTF minimalissimo.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".ttf",
        delete=False,
        dir=tempfile.gettempdir()
    ) as tmp:
        tmp.write(b"PLACEHOLDER_TTF_FILE")
        return Path(tmp.name)


@pytest.fixture(autouse=True)
def cleanup_resources_between_tests():
    """Auto-cleanup: esegue gc.collect() tra un test e l'altro.

    Questo previene contaminazione di stato quando i test vengono
    eseguiti in sequenza, specialmente importante per test che
    controllano il numero di file handle aperti.
    """
    gc.collect()  # Cleanup prima del test
    yield
    gc.collect()  # Cleanup dopo il test


@pytest.fixture(autouse=True)
def _neutralize_modal_dialogs(monkeypatch):
    """Rende non bloccanti tutti i dialog modali durante i test.

    On headless CI runners (e.g., GitHub Actions with QT_QPA_PLATFORM=offscreen),
    any QMessageBox.exec() or QDialog.exec() modal call blocks forever because
    there is no user to dismiss the dialog. This fixture neutralizes all modal
    dialogs globally so no test can hang indefinitely on a modal interaction.

    Tests can still override this locally with targeted monkeypatch if they need
    to assert on specific dialog behavior.
    """
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    )
    monkeypatch.setattr(
        QMessageBox, "about", staticmethod(lambda *a, **k: None)
    )
    monkeypatch.setattr(QMessageBox, "exec", lambda self, *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QDialog, "exec", lambda self, *a, **k: QDialog.DialogCode.Accepted.value)
    yield


@pytest.fixture(scope="session", autouse=True)
def generate_fixtures():
    _ensure_fixtures()


@pytest.fixture(scope="session")
def temp_bundled_font() -> Path:
    """
    Crea un temporary file che farà da placeholder per il font TTF.
    Ritorna un Path al file.
    """
    tmp_path = _create_minimal_ttf_file()
    yield tmp_path
    # Cleanup after session
    tmp_path.unlink(missing_ok=True)


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


@pytest.fixture(autouse=True)
def mock_bundled_font_for_tests(temp_bundled_font, monkeypatch, request):
    """
    Auto-setup per mocking la registrazione dei font.
    Solo per test_font_manager.py, non per altri test.

    Strategy:
    1. Mocka BUNDLED_FONT_PATH per puntare al file temporaneo
    2. Mocka TTFont solo quando viene usato con il bundled font path
    3. Mocka getRegisteredFontNames() per includere solo font del test corrente
    """
    # Skip font mocking per test che non lo richiedono
    if "test_font_manager" not in str(request.fspath):
        # Non-font-manager tests: just reset FontManager singleton, don't mock
        from utils.font_manager import get_font_manager
        fm = get_font_manager()
        fm.clear_bundled_fonts()
        yield
        return

    # Font manager tests: apply full mocking
    from reportlab.pdfbase import pdfmetrics, ttfonts

    from utils import config
    from utils.font_manager import FontManager, get_font_manager

    # Mock BUNDLED_FONT_PATH
    monkeypatch.setattr(config, "BUNDLED_FONT_PATH", temp_bundled_font)

    # Tracking fonts per il test corrente
    test_mocked_fonts = {}

    # Reset FontManager singleton at start of test
    fm = get_font_manager()
    fm.clear_bundled_fonts()

    # Salva il TTFont originale
    original_ttfont = ttfonts.TTFont

    # Crea un wrapper TTFont intelligente
    def smart_ttfont_wrapper(name, filepath, *args, **kwargs):
        """
        Wrapper che mocka solo i file bundled validi.
        """
        # Se è il bundled font path, usa il mock
        if filepath == str(temp_bundled_font):
            mock_font = MagicMock()
            mock_font.fontName = name
            mock_font.filepath = filepath
            return mock_font
        else:
            # Per altri path, usa il TTFont originale
            return original_ttfont(name, filepath, *args, **kwargs)

    # Patch TTFont dove viene usato nel font_manager
    monkeypatch.setattr(
        "utils.font_manager.TTFont",
        smart_ttfont_wrapper
    )

    # Patch registerFont per tracciare i font registrati
    original_register = pdfmetrics.registerFont

    def mock_register(font_obj):
        """Mock che registra il font nel nostro tracker."""
        if hasattr(font_obj, "fontName"):
            test_mocked_fonts[font_obj.fontName] = font_obj
        # Chiama l'originale
        try:
            original_register(font_obj)
        except Exception:
            pass

    monkeypatch.setattr(pdfmetrics, "registerFont", mock_register)

    # Patch getRegisteredFontNames per mostrare SOLO font di questo test
    # Questo evita contaminazione tra test
    original_get_registered = pdfmetrics.getRegisteredFontNames

    def mock_get_registered_font_names():
        """
        Ritorna SOLO i font registrati in questo test (test_mocked_fonts).
        Ignora i font da test precedenti per evitare contaminazione.
        """
        # Ritorna solo i font che abbiamo registrato in questo test
        return list(test_mocked_fonts.keys())

    monkeypatch.setattr(
        pdfmetrics,
        "getRegisteredFontNames",
        mock_get_registered_font_names
    )

    yield

    # Cleanup dopo il test
    test_mocked_fonts.clear()

    # CRITICO: Clear reportlab's pdfmetrics registry of the mocked font
    # This is essential because pdfmetrics.registerFont() adds objects to a
    # global registry that persists even after monkeypatch is undone.
    # The mocked TTFont is a MagicMock that returns MagicMock for stringWidth(),
    # causing TypeError in subsequent code that expects a float.
    try:
        from reportlab.pdfbase import pdfmetrics
        # Remove PDFusionFont if it exists and is a MagicMock
        if 'PDFusionFont' in pdfmetrics._fonts:
            font_obj = pdfmetrics._fonts['PDFusionFont']
            # Check if it's a MagicMock (not a real font)
            if hasattr(font_obj, '_mock_name'):
                del pdfmetrics._fonts['PDFusionFont']
    except Exception:
        pass

    # CRITICO: Reset BOTH singleton mechanisms in FontManager
    # There are two: FontManager._instance (class variable) and
    # _font_manager (module-level variable used by get_font_manager)
    # Both must be reset to prevent MagicMock cache contamination
    try:
        import utils.font_manager as fm_module
        fm_module._font_manager = None  # Reset module-level singleton
        from utils.font_manager import FontManager
        FontManager._instance = None  # Reset class-level singleton
    except Exception:
        pass

    # NOTE: Module reload (Soluzione 5) is handled by a module-scoped fixture
    # in test_font_manager.py that runs after all tests in that module complete.
    # This avoids breaking the singleton pattern during test_font_manager tests.
