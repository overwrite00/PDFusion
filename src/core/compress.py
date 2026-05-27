from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import fitz  # PyMuPDF
import pikepdf
from PIL import Image

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.temp_manager import atomic_write

logger = logging.getLogger(__name__)


class CompressPreset(Enum):
    SCREEN = "screen"  # 72 dpi — solo schermo, dimensione minima
    EBOOK = "ebook"  # 150 dpi — default consigliato
    PRINTER = "printer"  # 300 dpi — stampa normale
    PREPRESS = "prepress"  # 300 dpi — stampa professionale, qualità massima
    CUSTOM = "custom"  # parametri manuali


_PRESET_DPI = {
    CompressPreset.SCREEN: 72,
    CompressPreset.EBOOK: 150,
    CompressPreset.PRINTER: 300,
    CompressPreset.PREPRESS: 300,
}

_PRESET_QUALITY = {
    CompressPreset.SCREEN: 60,
    CompressPreset.EBOOK: 75,
    CompressPreset.PRINTER: 85,
    CompressPreset.PREPRESS: 95,
}


@dataclass
class CompressConfig:
    preset: CompressPreset = CompressPreset.EBOOK
    # Parametri custom (ignorati se preset != CUSTOM)
    custom_dpi: int = 150
    custom_jpeg_quality: int = 75
    remove_metadata: bool = False
    flatten_annotations: bool = False

    @property
    def dpi(self) -> int:
        if self.preset == CompressPreset.CUSTOM:
            return max(36, min(600, self.custom_dpi))
        return _PRESET_DPI[self.preset]

    @property
    def jpeg_quality(self) -> int:
        if self.preset == CompressPreset.CUSTOM:
            return max(10, min(100, self.custom_jpeg_quality))
        return _PRESET_QUALITY[self.preset]


def compress(
    input_path: Path,
    output_path: Path,
    config: CompressConfig | None = None,
    password: str | None = None,
) -> Path:
    """
    Comprime il PDF ottimizzando immagini e struttura interna.

    Strategia:
    1. PyMuPDF: riduce le immagini embedded al DPI target (JPEG).
    2. pikepdf: rimuove oggetti duplicati, garbage collect, deflate.
    3. Opzionale: rimuove metadati, appiattisce annotazioni.

    Returns:
        output_path.
    """
    if config is None:
        config = CompressConfig()

    doc = None
    pdf = None
    try:
        try:
            doc = fitz.open(str(input_path))
        except fitz.FileNotFoundError:
            raise PDFusionError(f"File non trovato: {input_path}")
        except Exception as exc:
            raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

        _resample_images(doc, config)

        if config.flatten_annotations:
            _flatten_annotations(doc)

        # Salva il PDF ricompresso in un buffer intermedio via PyMuPDF
        buf = io.BytesIO()
        doc.save(
            buf,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            garbage=4,
            clean=True,
        )
        buf.seek(0)
        doc.close()
        doc = None

        # Secondo passaggio con pikepdf: garbage collect + strip metadati
        pdf = pikepdf.Pdf.open(buf)
        if config.remove_metadata:
            _strip_metadata(pdf)

        with atomic_write(output_path) as tmp:
            pdf.save(
                tmp,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                recompress_flate=True,
            )
        pdf.close()
        pdf = None

    finally:
        # Cleanup fitz document
        if doc is not None:
            try:
                doc.close()
            except Exception as exc:
                logger.warning(f"Errore durante chiusura fitz Document: {exc}")

        # Cleanup pikepdf document
        if pdf is not None:
            try:
                pdf.close()
            except Exception as exc:
                logger.warning(f"Errore durante chiusura pikepdf Pdf: {exc}")

    return output_path


def _resample_images(doc: fitz.Document, config: CompressConfig) -> None:
    """Riduce la risoluzione delle immagini embedded al DPI target."""
    dpi = config.dpi
    quality = config.jpeg_quality

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except (ValueError, KeyError, RuntimeError):
                # Immagine corrotta o formato inaspettato nel PDF
                continue

            img_bytes = base_image["image"]
            img_ext = base_image["ext"]

            # Salta immagini già piccole o non rasterizzate
            if img_ext in ("jpx", "jb2"):
                continue

            try:
                pil_img = Image.open(io.BytesIO(img_bytes))
            except (OSError, Image.UnidentifiedImageError):
                # Formato immagine non supportato o dati corrotti
                continue

            orig_w, orig_h = pil_img.size

            # Stima il DPI effettivo dell'immagine nella pagina
            # (approssimazione basata sulla dimensione della pagina in punti)
            page_rect = page.rect
            scale_x = orig_w / page_rect.width if page_rect.width > 0 else 1
            effective_dpi = scale_x * 72  # 1 punto PDF = 1/72 pollice

            if effective_dpi <= dpi * 1.1:
                continue  # già al DPI target, non ridimensionare

            scale = dpi / effective_dpi
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))

            try:
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                if pil_img.mode == "RGBA":
                    pil_img = pil_img.convert("RGB")

                out_buf = io.BytesIO()
                pil_img.save(out_buf, format="JPEG", quality=quality, optimize=True)
                out_buf.seek(0)

                doc.replace_image(xref, stream=out_buf.read())
            except (OSError, ValueError):
                # Errore durante ridimensionamento, conversione o salvataggio
                # Salta l'immagine e continua con il resto del documento
                continue


def _flatten_annotations(doc: fitz.Document) -> None:
    """Appiattisce le annotazioni (stampa il loro aspetto nella pagina)."""
    for page in doc:
        annots = list(page.annots())
        for annot in annots:
            annot.set_flags(0)
        page.clean_contents()


def _strip_metadata(pdf: pikepdf.Pdf) -> None:
    """Rimuove i metadati docinfo e XMP."""
    with pdf.open_metadata() as xmp:
        for key in list(xmp.keys()):
            try:
                del xmp[key]
            except Exception:
                pass
    # pikepdf.Dictionary non supporta .clear(); rimuoviamo ogni chiave singolarmente
    for key in list(pdf.docinfo.keys()):
        try:
            del pdf.docinfo[key]
        except Exception:
            pass
