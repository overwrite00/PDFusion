"""
Genera i PDF fixture usati dalla test suite.
Eseguire una volta: python tests/fixtures/create_fixtures.py
"""
from pathlib import Path

import pikepdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

FIXTURES = Path(__file__).parent


def _make_simple_pdf(path: Path, num_pages: int, title: str = "") -> None:
    """Crea un PDF con N pagine via reportlab."""
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    for i in range(1, num_pages + 1):
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(w / 2, h / 2 + 20, title or path.stem)
        c.setFont("Helvetica", 16)
        c.drawCentredString(w / 2, h / 2 - 20, f"Pagina {i} di {num_pages}")
        c.showPage()
    c.save()


def create_sample() -> None:
    """sample.pdf — 1 pagina, non cifrato."""
    _make_simple_pdf(FIXTURES / "sample.pdf", 1, "Sample PDF")
    print("sample.pdf creato")


def create_multipage() -> None:
    """multipage.pdf — 10 pagine, non cifrato."""
    _make_simple_pdf(FIXTURES / "multipage.pdf", 10, "Multipage PDF")
    print("multipage.pdf creato")


def create_encrypted() -> None:
    """encrypted.pdf — 1 pagina, password utente 'test123'."""
    tmp = FIXTURES / "_tmp_enc_source.pdf"
    _make_simple_pdf(tmp, 1, "Encrypted PDF")
    with pikepdf.open(tmp) as pdf:
        pdf.save(
            str(FIXTURES / "encrypted.pdf"),
            encryption=pikepdf.Encryption(
                user="test123",
                owner="owner456",
                R=4,
            ),
        )
    tmp.unlink()
    print("encrypted.pdf creato")


def create_with_images() -> None:
    """with_images.pdf — 2 pagine con testo + rettangoli colorati (simulano immagini)."""
    from reportlab.lib.colors import Color

    path = FIXTURES / "with_images.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    for page in range(1, 3):
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(w / 2, h - 80, f"With Images — Page {page}")
        # Rettangolo che simula un'immagine incorporata
        c.setFillColor(Color(0.2, 0.4, 0.8, alpha=1))
        c.rect(100, h / 2 - 100, w - 200, 200, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica", 14)
        c.drawCentredString(w / 2, h / 2, "Immagine simulata")
        c.showPage()
    c.save()
    print("with_images.pdf creato")


if __name__ == "__main__":
    FIXTURES.mkdir(parents=True, exist_ok=True)
    create_sample()
    create_multipage()
    create_encrypted()
    create_with_images()
    print("\nTutti i fixture creati in", FIXTURES)
