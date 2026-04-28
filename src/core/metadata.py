from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pikepdf

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.temp_manager import atomic_write


@dataclass
class PDFMetadata:
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    mod_date: Optional[str] = None


def read_metadata(
    input_path: Path,
    password: Optional[str] = None,
) -> PDFMetadata:
    """
    Legge i metadati (docinfo) dal PDF.

    Returns:
        PDFMetadata con i campi disponibili.
    """
    try:
        kwargs = {"password": password} if password else {}
        pdf = pikepdf.open(input_path, **kwargs)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    try:
        info = pdf.docinfo
        meta = PDFMetadata(
            title=_get_str(info, "/Title"),
            author=_get_str(info, "/Author"),
            subject=_get_str(info, "/Subject"),
            keywords=_get_str(info, "/Keywords"),
            creator=_get_str(info, "/Creator"),
            producer=_get_str(info, "/Producer"),
            creation_date=_get_str(info, "/CreationDate"),
            mod_date=_get_str(info, "/ModDate"),
        )
    finally:
        pdf.close()

    return meta


def write_metadata(
    input_path: Path,
    metadata: PDFMetadata,
    output_path: Path,
    password: Optional[str] = None,
) -> Path:
    """
    Scrive i metadati nel PDF.

    Campi `None` nel dataclass vengono ignorati (non sovrascritti).
    Passa una stringa vuota "" per cancellare un campo esistente.

    Returns:
        output_path.
    """
    try:
        kwargs = {"password": password} if password else {}
        pdf = pikepdf.open(input_path, **kwargs)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    try:
        with pdf.open_metadata(set_pikepdf_as_editor=False) as xmp:
            info = pdf.docinfo

            _set_field(info, xmp, "/Title", "dc:title", metadata.title)
            _set_field(info, xmp, "/Author", "dc:creator", metadata.author)
            _set_field(info, xmp, "/Subject", "dc:description", metadata.subject)
            _set_field(info, xmp, "/Keywords", "pdf:Keywords", metadata.keywords)
            _set_field(info, xmp, "/Creator", "xmp:CreatorTool", metadata.creator)

        with atomic_write(output_path) as tmp:
            pdf.save(tmp)
    finally:
        pdf.close()

    return output_path


def _get_str(info: pikepdf.Dictionary, key: str) -> Optional[str]:
    try:
        val = info.get(key)
        if val is None:
            return None
        return str(val)
    except Exception:
        return None


def _set_field(
    info: pikepdf.Dictionary,
    xmp,
    docinfo_key: str,
    xmp_key: str,
    value: Optional[str],
) -> None:
    if value is None:
        return
    if value == "":
        info.pop(docinfo_key, None)
        try:
            del xmp[xmp_key]
        except (KeyError, Exception):
            pass
    else:
        info[docinfo_key] = value
        try:
            xmp[xmp_key] = value
        except Exception:
            pass
