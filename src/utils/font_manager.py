"""
Font Manager Singleton — Gestione centralizzata e idempotente della registrazione dei font.

Risolve il problema di accumulation nella pdfmetrics registry in operazioni batch.
Un singolo FontManager controlla tutti i registri per evitare duplicate registrations.
"""
from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


class FontManager:
    """
    Singleton per gestire la registrazione dei font in reportlab.

    Garantisce:
    - Registrazione idempotente (chiamate ripetute non causano duplicati)
    - Thread-safe tramite lock
    - Fallback a Helvetica se il font bundled non è disponibile
    - Logging centralizzato
    """

    _instance: FontManager | None = None
    _lock: Lock = Lock()
    _registry_lock: Lock = Lock()  # Lock separato per operazioni registry

    def __new__(cls) -> FontManager:
        """Implementa pattern singleton thread-safe."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Inizializza il manager una sola volta."""
        if getattr(self, '_initialized', False):
            return
        self._initialized = True
        self._registered_fonts: dict[str, str] = {}  # {font_name: path}
        logger.debug("FontManager singleton inizializzato")

    def register_bundled_font(
        self,
        font_name: str = "PDFusionFont",
        font_path: Path | None = None,
    ) -> str:
        """
        Registra un font bundled in modo idempotente.

        Args:
            font_name: Nome del font da registrare (default: "PDFusionFont")
            font_path: Path al file TTF. Se None, carica dal path di default.

        Returns:
            Nome del font registrato (font_name se successo, "Helvetica" se fallback)

        Garanzie:
            - Idempotente: chiamate ripetute non creano duplicati in registry
            - Thread-safe: sincronizzato con lock
            - Fallback graceful: Helvetica se file mancante o corrotto
        """
        # Importa il default se non passato
        if font_path is None:
            from utils.config import BUNDLED_FONT_PATH
            font_path = BUNDLED_FONT_PATH

        # Check con lock per thread-safety
        with self._registry_lock:
            # Idempotenza: se già registrato, return il nome
            if font_name in pdfmetrics.getRegisteredFontNames():
                logger.debug(f"Font '{font_name}' già registrato, return idempotente")
                return font_name

            # Se mancante, fallback a Helvetica
            if not font_path.exists():
                logger.warning(f"Font bundled non trovato: {font_path}, fallback a Helvetica")
                return "Helvetica"

            # Prova registrazione
            try:
                ttfont = TTFont(font_name, str(font_path))
                pdfmetrics.registerFont(ttfont)
                self._registered_fonts[font_name] = str(font_path)
                logger.info(f"Font '{font_name}' registrato: {font_path}")
                return font_name
            except Exception as exc:
                logger.error(
                    f"Errore registrazione font '{font_name}' ({font_path}): {exc}",
                    exc_info=True,
                )
                return "Helvetica"

    def get_font(self, font_name: str = "PDFusionFont") -> str:
        """
        Ritorna il nome del font registrato o "Helvetica" se non disponibile.

        Utile quando si vuole semplicemente leggere il font senza registrarlo di nuovo.

        Args:
            font_name: Nome del font da verificare

        Returns:
            font_name se registrato, "Helvetica" altrimenti
        """
        with self._registry_lock:
            if font_name in pdfmetrics.getRegisteredFontNames():
                return font_name
        return "Helvetica"

    def is_registered(self, font_name: str) -> bool:
        """Verifica se un font è registrato in pdfmetrics."""
        with self._registry_lock:
            return font_name in pdfmetrics.getRegisteredFontNames()

    def get_registered_fonts(self) -> list[str]:
        """Ritorna la lista di tutti i font registrati."""
        with self._registry_lock:
            return list(pdfmetrics.getRegisteredFontNames())

    def clear_bundled_fonts(self) -> None:
        """
        Rimuove dal tracking interno i font bundled.

        NOTA: Non rimuove dalla registry pdfmetrics (non è possibile).
        Utile per testing.
        """
        self._registered_fonts.clear()
        logger.debug("Tracking interno dei font bundled azzerato")


# Istanza globale singleton
_font_manager: FontManager | None = None


def get_font_manager() -> FontManager:
    """Factory function per ottenere l'istanza singleton del FontManager."""
    global _font_manager
    if _font_manager is None:
        _font_manager = FontManager()
    return _font_manager
