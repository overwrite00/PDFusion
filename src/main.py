import sys
from pathlib import Path

# Aggiunge src/ al path così tutti i moduli trovano i propri import
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from styles.theme import apply_theme
from utils.config import APP_NAME, VERSION
from utils.temp_manager import cleanup_temp


def main() -> None:
    # Abilita HiDPI prima di creare QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("PDFusion")

    # Applica il tema prima di qualsiasi widget
    apply_theme(app)

    # Pulizia file temporanei orfani da sessioni precedenti
    cleanup_temp()

    # Import qui per evitare import circolari al top-level
    from ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
