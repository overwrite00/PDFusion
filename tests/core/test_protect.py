import pikepdf
import pytest

from core.protect import EncryptionLevel, ProtectConfig, protect, remove_protection
from utils.exceptions import PDFusionError


class TestProtect:
    def test_protect_with_user_password(self, sample_pdf, tmp_output):
        cfg = ProtectConfig(user_password="secret")
        result = protect(sample_pdf, tmp_output, cfg)
        assert result.exists()
        with pytest.raises(pikepdf.PasswordError):
            pikepdf.open(result)
        with pikepdf.open(result, password="secret") as pdf:
            assert len(pdf.pages) == 1

    def test_protect_aes256(self, sample_pdf, tmp_output):
        cfg = ProtectConfig(
            user_password="pass",
            encryption=EncryptionLevel.AES_256,
        )
        result = protect(sample_pdf, tmp_output, cfg)
        with pikepdf.open(result, password="pass") as pdf:
            assert len(pdf.pages) == 1

    def test_protect_owner_only(self, sample_pdf, tmp_output):
        cfg = ProtectConfig(owner_password="owner", allow_copy=False)
        result = protect(sample_pdf, tmp_output, cfg)
        # Con solo owner_password, il PDF può essere aperto senza password utente
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_no_password_no_restrictions_raises(self, sample_pdf, tmp_output):
        # ProtectConfig con tutte le restrizioni aperte e nessuna password → deve sollevare
        cfg = ProtectConfig(
            allow_print=True,
            allow_print_highres=True,
            allow_copy=True,
            allow_edit=True,
            allow_annotations=True,
            allow_forms=True,
        )
        with pytest.raises(PDFusionError):
            protect(sample_pdf, tmp_output, cfg)


class TestRemoveProtection:
    def test_remove_user_password(self, encrypted_pdf, tmp_output):
        result = remove_protection(encrypted_pdf, tmp_output, password="test123")
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_wrong_password_raises(self, encrypted_pdf, tmp_output):
        with pytest.raises(PDFusionError):
            remove_protection(encrypted_pdf, tmp_output, password="wrong")
