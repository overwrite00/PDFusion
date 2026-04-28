from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# Palette hex
# ---------------------------------------------------------------------------
class Colors:
    # Sfondi
    BG_MAIN = "#F5F4F1"
    BG_SIDEBAR = "#ECEAE5"
    BG_VIEWER = "#E8E6E0"
    BG_CARD = "#FFFFFF"
    BG_HOVER = "#F0EEE9"

    # Accent
    ACCENT = "#4A6FA5"
    ACCENT_HOVER = "#3A5A8C"
    ACCENT_LIGHT = "#D0DCF0"

    # Testo
    TEXT_PRIMARY = "#1E1E2E"
    TEXT_SECONDARY = "#6B7280"
    TEXT_DISABLED = "#B0AEA7"

    # Bordi
    BORDER = "#D8D5CE"
    BORDER_FOCUS = "#4A6FA5"

    # Stato
    SUCCESS = "#2E7D52"
    WARNING = "#C07A20"
    ERROR = "#B5383A"


def apply_theme(app: QApplication) -> None:
    """
    Applica il tema PDFusion all'applicazione.
    Da chiamare subito dopo QApplication() e prima di qualsiasi widget.
    """
    app.setStyle("Fusion")

    palette = QPalette()

    bg = QColor(Colors.BG_MAIN)
    accent = QColor(Colors.ACCENT)
    text = QColor(Colors.TEXT_PRIMARY)
    text_disabled = QColor(Colors.TEXT_DISABLED)
    border = QColor(Colors.BORDER)

    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_HOVER))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(Colors.BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, bg)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(Colors.BG_CARD))
    palette.setColor(QPalette.ColorRole.Link, accent)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Colors.BG_CARD))

    # Stato disabilitato
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, text_disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, text_disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, text_disabled)

    app.setPalette(palette)

    # Carica il QSS dalla stessa directory e inietta i path assoluti delle icone SVG
    from pathlib import Path

    qss_path = Path(__file__).parent / "pdfusion.qss"
    if qss_path.exists():
        icons_dir = Path(__file__).parent.parent.parent / "assets" / "icons"

        def _url(name: str) -> str:
            """Converte un path in forward-slash per url() del QSS."""
            return str(icons_dir / name).replace("\\", "/")

        qss = qss_path.read_text(encoding="utf-8")
        qss = qss.replace("ICON_ARROW_UP_DIS", _url("arrow_up_dis.svg"))
        qss = qss.replace("ICON_ARROW_DOWN_DIS", _url("arrow_down_dis.svg"))
        qss = qss.replace("ICON_ARROW_UP", _url("arrow_up.svg"))
        qss = qss.replace("ICON_ARROW_DOWN", _url("arrow_down.svg"))
        app.setStyleSheet(qss)
