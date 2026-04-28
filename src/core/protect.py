from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import pikepdf

from utils.exceptions import PDFusionError, UnsupportedFormatError
from utils.temp_manager import atomic_write


class EncryptionLevel(Enum):
    AES_128 = "aes128"   # default consigliato, compatibilità massima
    AES_256 = "aes256"   # più sicuro, richiede Acrobat 9+


@dataclass
class ProtectConfig:
    user_password: str = ""         # password per aprire il documento
    owner_password: str = ""        # password per modificare i permessi
    encryption: EncryptionLevel = EncryptionLevel.AES_128
    allow_print: bool = True        # permetti stampa
    allow_print_highres: bool = True  # permetti stampa ad alta risoluzione
    allow_copy: bool = False         # permetti copia del testo
    allow_edit: bool = False         # permetti modifiche al contenuto
    allow_annotations: bool = False  # permetti aggiunta annotazioni
    allow_forms: bool = False        # permetti compilazione moduli


def protect(
    input_path: Path,
    output_path: Path,
    config: ProtectConfig,
    password: Optional[str] = None,
) -> Path:
    """
    Applica protezione password e restrizioni di permesso al PDF.

    Se config.user_password e config.owner_password sono entrambi vuoti,
    viene usata una owner_password casuale per applicare solo i permessi.

    Returns:
        output_path.

    Raises:
        PDFusionError: se entrambe le password sono vuote e non ci sono
                       restrizioni da applicare (operazione inutile).
    """
    if (not config.user_password and not config.owner_password
            and _all_permissions_granted(config)):
        raise PDFusionError(
            "Specifica almeno una password o una restrizione da applicare."
        )

    try:
        kwargs = {"password": password} if password else {}
        pdf = pikepdf.open(input_path, **kwargs)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata o mancante per aprire il PDF.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    try:
        permissions = _build_permissions(config)
        encryption = _build_encryption(config, permissions)

        with atomic_write(output_path) as tmp:
            pdf.save(tmp, encryption=encryption)
    finally:
        pdf.close()

    return output_path


def remove_protection(
    input_path: Path,
    output_path: Path,
    password: str,
) -> Path:
    """
    Rimuove la protezione da un PDF (richiede la owner password).

    Returns:
        output_path senza protezione.
    """
    try:
        pdf = pikepdf.open(input_path, password=password)
    except pikepdf.PasswordError:
        raise PDFusionError("Password errata: impossibile rimuovere la protezione.")
    except pikepdf.PdfError as exc:
        raise UnsupportedFormatError(f"File non valido: {input_path.name}") from exc

    try:
        with atomic_write(output_path) as tmp:
            pdf.save(tmp)  # salva senza encryption
    finally:
        pdf.close()

    return output_path


def _build_permissions(config: ProtectConfig) -> pikepdf.Permissions:
    return pikepdf.Permissions(
        print_lowres=config.allow_print,
        print_highres=config.allow_print_highres,
        extract=config.allow_copy,
        modify_other=config.allow_edit,
        modify_annotation=config.allow_annotations,
        modify_form=config.allow_forms,
        accessibility=True,          # sempre abilitato per accessibilità
        modify_assembly=config.allow_edit,
    )


def _build_encryption(
    config: ProtectConfig,
    permissions: pikepdf.Permissions,
) -> pikepdf.Encryption:
    user_pw = config.user_password
    owner_pw = config.owner_password or _generate_owner_password()

    if config.encryption == EncryptionLevel.AES_256:
        return pikepdf.Encryption(
            user=user_pw,
            owner=owner_pw,
            R=6,
            allow=permissions,
        )
    else:  # AES_128
        return pikepdf.Encryption(
            user=user_pw,
            owner=owner_pw,
            R=4,
            allow=permissions,
        )


def _generate_owner_password() -> str:
    import secrets
    return secrets.token_urlsafe(24)


def _all_permissions_granted(config: ProtectConfig) -> bool:
    return all([
        config.allow_print,
        config.allow_print_highres,
        config.allow_copy,
        config.allow_edit,
        config.allow_annotations,
        config.allow_forms,
    ])
