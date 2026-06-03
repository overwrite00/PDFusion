from dataclasses import dataclass
from pathlib import Path

import pikepdf

from core.pdf_opener import open_pdf_safe
from utils.temp_manager import atomic_write


@dataclass
class PDFMetadata:
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: str | None = None
    mod_date: str | None = None


def read_metadata(
    input_path: Path,
    password: str | None = None,
) -> PDFMetadata:
    """
    Legge i metadati (docinfo) dal PDF.

    Returns:
        PDFMetadata con i campi disponibili.
    """
    pdf = open_pdf_safe(input_path, password)

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
    password: str | None = None,
) -> Path:
    """
    Scrive i metadati nel PDF.

    Campi `None` nel dataclass vengono ignorati (non sovrascritti).
    Passa una stringa vuota "" per cancellare un campo esistente.

    Returns:
        output_path.
    """
    pdf = open_pdf_safe(input_path, password)

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


def _get_str(info: pikepdf.Dictionary, key: str) -> str | None:
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
    value: str | None,
) -> None:
    if value is None:
        return
    if value == "":
        try:
            del info[docinfo_key]
        except (KeyError, Exception):
            pass
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
