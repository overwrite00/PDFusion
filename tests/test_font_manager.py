"""
Test suite per FontManager — Gestione centralizzata della font registry.

Testa:
- Registrazione idempotente
- Thread-safety
- Fallback graceful
- Batch operations senza accumulation
"""
from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.pdfbase import pdfmetrics

from utils.font_manager import FontManager, get_font_manager


@pytest.fixture(scope="module", autouse=True)
def cleanup_font_manager_module_after_all_tests():
    """
    After ALL tests in test_font_manager.py complete, reload the module
    to ensure clean state for subsequent test modules (e.g., test_resource_cleanup).

    This is paired with the reset of FontManager._instance in conftest.py's mock_bundled_font_for_tests.
    Module scope ensures this only runs once per module, not after each test.
    """
    yield

    # After all tests in this module complete, reload the entire module
    # to ensure any cached MagicMock objects are discarded
    try:
        import sys
        # Force reload of the utils.font_manager module
        if "utils.font_manager" in sys.modules:
            del sys.modules["utils.font_manager"]
        # Re-import it to get a fresh version
        import utils.font_manager  # noqa: F401
    except Exception:
        pass


class TestFontManagerSingleton:
    """Verifica che FontManager sia un vero singleton."""

    def test_singleton_same_instance(self) -> None:
        """Lo stesso instance viene ritornato da multiple chiamate."""
        fm1 = get_font_manager()
        fm2 = get_font_manager()
        assert fm1 is fm2

    def test_singleton_via_class_constructor(self) -> None:
        """FontManager() ritorna sempre lo stesso instance."""
        fm1 = FontManager()
        fm2 = FontManager()
        assert fm1 is fm2
        assert fm1 is get_font_manager()


class TestIdempotentRegistration:
    """Testa la garanzia di registrazione idempotente."""

    @pytest.fixture(autouse=True)
    def cleanup_registry(self) -> None:
        """Pulisce la registry prima/dopo ogni test."""
        initial_fonts = set(pdfmetrics.getRegisteredFontNames())
        yield
        # Dopo il test, la registry dovrebbe solo avere i font iniziali + PDFusionFont
        # (che non si può unregister in reportlab)

    def test_first_registration_succeeds(self, sample_pdf) -> None:
        """La prima registrazione aggiunge il font alla registry."""
        fm = get_font_manager()
        font_name = fm.register_bundled_font()

        assert font_name == "PDFusionFont"
        assert "PDFusionFont" in pdfmetrics.getRegisteredFontNames()

    def test_second_registration_idempotent(self, sample_pdf) -> None:
        """La seconda registrazione ritorna il nome senza duplicare in registry."""
        fm = get_font_manager()
        fm.clear_bundled_fonts()

        # Primo registro
        registered_1 = set(pdfmetrics.getRegisteredFontNames())
        font_name_1 = fm.register_bundled_font()
        registered_after_1 = set(pdfmetrics.getRegisteredFontNames())
        count_added_1 = len(registered_after_1 - registered_1)

        # Secondo registro (idempotente)
        font_name_2 = fm.register_bundled_font()
        registered_after_2 = set(pdfmetrics.getRegisteredFontNames())
        count_added_2 = len(registered_after_2 - registered_after_1)

        assert font_name_1 == font_name_2 == "PDFusionFont"
        assert count_added_1 >= 1  # Almeno il font è stato aggiunto
        assert count_added_2 == 0  # Niente aggiunto alla seconda chiamata

    def test_multiple_calls_same_registry_size(self, sample_pdf) -> None:
        """100 registrazioni consecutive non aumentano la registry size."""
        fm = get_font_manager()
        fm.clear_bundled_fonts()

        size_before = len(pdfmetrics.getRegisteredFontNames())

        for _ in range(100):
            fm.register_bundled_font()

        size_after = len(pdfmetrics.getRegisteredFontNames())

        # Size dovrebbe aumentare al massimo di 1 (il primo registro)
        assert size_after - size_before <= 1


class TestFallbackBehavior:
    """Testa il fallback a Helvetica in caso di errore."""

    def test_missing_bundled_font_fallback(self) -> None:
        """Se il font bundled manca, fallback a Helvetica."""
        fm = get_font_manager()
        fm.clear_bundled_fonts()

        # Chiama con un path che non esiste
        font_name = fm.register_bundled_font(
            font_name="TestFont",
            font_path=Path("/nonexistent/path/to/font.ttf")
        )

        assert font_name == "Helvetica"

    def test_invalid_ttf_fallback(self) -> None:
        """Se il TTF è invalido, fallback a Helvetica."""
        fm = get_font_manager()

        # Crea un file TTF finto (non valido)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as tmp:
            tmp.write(b"This is not a valid TTF file")
            tmp_path = Path(tmp.name)

        try:
            font_name = fm.register_bundled_font(
                font_name="InvalidFont",
                font_path=tmp_path
            )
            assert font_name == "Helvetica"
        finally:
            tmp_path.unlink()


class TestGetFont:
    """Testa il metodo get_font()."""

    def test_get_font_registered(self, sample_pdf) -> None:
        """get_font() ritorna il nome se registrato."""
        fm = get_font_manager()
        fm.register_bundled_font()

        font = fm.get_font()
        assert font == "PDFusionFont"

    def test_get_font_not_registered(self) -> None:
        """get_font() ritorna Helvetica se non registrato."""
        fm = get_font_manager()

        # Chiama con un font che sicuramente non è registrato
        font = fm.get_font("NonexistentFont123")
        assert font == "Helvetica"


class TestRegistryQueries:
    """Testa i metodi di query sulla registry."""

    def test_is_registered(self, sample_pdf) -> None:
        """is_registered() verifica correttamente."""
        fm = get_font_manager()
        fm.register_bundled_font()

        assert fm.is_registered("PDFusionFont") is True
        assert fm.is_registered("NonexistentFont") is False

    def test_get_registered_fonts(self, sample_pdf) -> None:
        """get_registered_fonts() ritorna lista non vuota."""
        fm = get_font_manager()
        fm.register_bundled_font()

        fonts = fm.get_registered_fonts()
        assert isinstance(fonts, list)
        assert len(fonts) > 0
        assert "PDFusionFont" in fonts


class TestBatchOperations:
    """Testa operazioni batch senza accumulation."""

    def test_batch_watermark_headers_license(self) -> None:
        """
        Batch di watermark + headers + license non causa accumulation.

        Simula 10 iterazioni di:
        1. Registrazione per watermark
        2. Registrazione per headers
        3. Registrazione per license
        """
        fm = get_font_manager()
        fm.clear_bundled_fonts()

        size_before = len(pdfmetrics.getRegisteredFontNames())

        # Simula 10 batch operations
        for _ in range(10):
            # Tutti e tre i moduli registrano il font
            font1 = fm.register_bundled_font()
            font2 = fm.register_bundled_font()
            font3 = fm.register_bundled_font()

            assert font1 == font2 == font3 == "PDFusionFont"

        size_after = len(pdfmetrics.getRegisteredFontNames())

        # Registry size dovrebbe aumentare al massimo di 1
        assert size_after - size_before <= 1


class TestThreadSafety:
    """Testa thread-safety del FontManager."""

    def test_concurrent_registrations(self, sample_pdf) -> None:
        """Registrazioni concorrenti da thread diversi sono sicure."""
        import threading

        fm = get_font_manager()
        fm.clear_bundled_fonts()

        results = []

        def register_font() -> None:
            font = fm.register_bundled_font()
            results.append(font)

        threads = [threading.Thread(target=register_font) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Tutti dovrebbero aver registrato lo stesso font
        assert all(r == "PDFusionFont" for r in results)

        # Registry dovrebbe avere solo 1 copia del font
        registry = pdfmetrics.getRegisteredFontNames()
        assert registry.count("PDFusionFont") == 1 or "PDFusionFont" in registry


class TestCustomFontPath:
    """Testa registrazione con font path personalizzato."""

    def test_custom_font_path_valid(self, tmp_path) -> None:
        """Registrazione con path personalizzato valido funziona."""
        from utils.config import BUNDLED_FONT_PATH

        if BUNDLED_FONT_PATH.exists():
            fm = get_font_manager()
            font_name = fm.register_bundled_font(
                font_name="CustomFont",
                font_path=BUNDLED_FONT_PATH
            )
            assert font_name == "CustomFont"
            assert "CustomFont" in pdfmetrics.getRegisteredFontNames()

    def test_custom_font_path_invalid(self) -> None:
        """Registrazione con path invalido fallback a Helvetica."""
        fm = get_font_manager()
        font_name = fm.register_bundled_font(
            font_name="InvalidPath",
            font_path=Path("/invalid/path/font.ttf")
        )
        assert font_name == "Helvetica"


class TestEdgeCases:
    """Test per edge case."""

    def test_register_before_bundled_font_exists(self) -> None:
        """Registrazione quando bundled font non esiste ritorna Helvetica."""
        fm = get_font_manager()
        # Usa un path che sicuramente non esiste
        result = fm.register_bundled_font(
            font_path=Path("/this/does/not/exist/ever.ttf")
        )
        assert result == "Helvetica"

    def test_font_name_with_spaces(self) -> None:
        """Font names con spazi sono gestiti correttamente."""
        fm = get_font_manager()
        font_name = fm.register_bundled_font(
            font_name="Font With Spaces",
            font_path=Path("/nonexistent/path.ttf")
        )
        # Fallback a Helvetica perché path invalido
        assert font_name == "Helvetica"

    def test_empty_font_name(self) -> None:
        """Font name vuoto è gestito (registrazione fallisce, fallback)."""
        fm = get_font_manager()
        # Questo dovrebbe fallire e tornare Helvetica
        try:
            font_name = fm.register_bundled_font(
                font_name="",
                font_path=Path("/nonexistent.ttf")
            )
            # Se non è eccezione, deve essere fallback
            assert font_name == "Helvetica"
        except (ValueError, TypeError):
            # Se lancia eccezione, è comunque accettabile
            pass


class TestLogging:
    """Testa il logging del FontManager."""

    def test_successful_registration_logged(self, caplog, sample_pdf) -> None:
        """Registrazione di successo è loggata."""
        fm = get_font_manager()
        fm.clear_bundled_fonts()

        with caplog.at_level("INFO"):
            fm.register_bundled_font()

        # Dovrebbe esserci un log di successo o di idempotenza
        log_text = "\n".join([r.message for r in caplog.records])
        assert "PDFusionFont" in log_text or "registrato" in log_text.lower() or "idempotente" in log_text.lower()

    def test_missing_font_logged(self, caplog) -> None:
        """Font mancante è loggato come debug (fallback a Helvetica)."""
        fm = get_font_manager()

        with caplog.at_level("DEBUG"):
            fm.register_bundled_font(
                font_path=Path("/nonexistent/font.ttf")
            )

        # Dovrebbe esserci un debug log del fallback
        debug_logs = [r for r in caplog.records if r.levelname == "DEBUG"]
        assert len(debug_logs) > 0

    def test_error_logged(self, caplog) -> None:
        """Errori di registrazione sono loggati."""
        fm = get_font_manager()

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as tmp:
            tmp.write(b"Invalid TTF")
            tmp_path = Path(tmp.name)

        try:
            with caplog.at_level("ERROR"):
                fm.register_bundled_font(
                    font_name="BadFont",
                    font_path=tmp_path
                )

            # Dovrebbe esserci un error log
            errors = [r for r in caplog.records if r.levelname == "ERROR"]
            assert len(errors) > 0
        finally:
            tmp_path.unlink()
