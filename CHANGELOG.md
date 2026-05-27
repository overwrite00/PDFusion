# Changelog

All notable changes to PDFusion are documented in this file.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`

For planned features, see [ROADMAP.md](ROADMAP.md).

---

## [Unreleased]

_No unreleased changes at this time._

---

## [0.2.0] — 2026-05-27

### Security
- Fixed race condition in main_window._on_operation_done() after _cleanup_all_temps() — added file existence guard in _on_preview_requested()
- Fixed thread timeout vulnerability in base_panel._discard_preview_tmp() — added fallback terminate() to prevent thread hang and resource leak
- Improved exception handling in compress and watermark modules to prevent silent failures masking critical errors

### Fixed
- **Resource leak**: fitz.open() in main_window._on_open_path() — added try-finally to guarantee document closure
- **Silent exception handling**: compress._resample_images() — replaced generic `except Exception:` with specific exceptions (PIL.UnidentifiedImageError, ValueError, IOError)
- **Error masking**: watermark._draw_image_watermark() — added logging and specific exception handling instead of silent pass

### Added
- **Testing**: 13 new UI tests for main_window (file opening, panel switching, memory management) with pytest-qt
- **Testing**: pytest-cov integration with coverage reporting (65%+ total, 85%+ core modules)
- **Testing**: mypy type checking configuration in pyproject.toml
- **Code Quality**: Helper function `_open_pdf_with_password()` in core/__init__.py for DRY principle
- **Documentation**: CONTRIBUTING.md with dev setup, PR workflow, code style guidelines
- **Development**: requirements-dev.txt now includes pytest-cov, mypy for automated code quality checks

### Changed
- **Code Style**: Applied ruff format and ruff check to all Python files (40 files formatted for PEP 8 compliance)
- **Imports**: Moved non-top-level imports to module level in main_window.py (PEP 8)
- **Error Handling**: Replaced generic `except Exception:` patterns with specific exception types in compress.py and watermark.py
- **Logging**: Added logging module imports to compress.py and watermark.py for error tracking

---

## [0.1.0] — 2025-01-01

### Added
- **Split PDF**: divisione ogni N pagine o per intervalli personalizzati (`1-3, 5, 7-9`)
- **Merge PDF**: unione di più file PDF in uno, con ordine personalizzabile
- **Delete pages**: eliminazione pagine singole o per intervallo, sia dal viewer che da input diretto
- **Insert page**: inserimento pagina bianca o da un altro PDF in posizione scelta
- **Compress PDF**: 5 preset (Screen 72dpi, eBook 150dpi, Printer 300dpi, Prepress 300dpi, Custom); downsampling immagini via Pillow + pikepdf garbage collection
- **Protect PDF**: protezione con password utente/proprietario, crittografia AES-128 (default) e AES-256; gestione permessi (stampa, copia, modifica)
- **Watermark**: testo (21 preset IT+EN) e immagine (PNG/SVG); 7 posizioni (CENTER_DIAGONAL, CENTER, TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT, TILED); opacità, rotazione, scala; selezione pagine (tutte, prima, ultima, prima+ultima, intervallo)
- **License page**: inserimento pagina di licenza in posizione 0; 11 tipi (Copyright, CC BY, CC BY-SA, CC BY-NC, CC BY-NC-SA, CC BY-ND, CC BY-NC-ND, CC0, MIT, Proprietary, Educational); template Jinja2 con variabili `author`, `year`, `title`
- **Headers & Footers**: intestazioni e piè di pagina con 3 zone (sinistra, centro, destra); variabili `{page}`, `{total}`, `{date}`, `{title}`, `{author}`; 5 preset formato; selezione pagine
- **Rotate**: rotazione pagine (90°/180°/270°) via pikepdf, senza re-render
- **Reorder pages**: riordinamento pagine con drag-and-drop nel thumbnail panel
- **Extract pages**: estrazione intervalli in un nuovo PDF
- **Metadata editor**: lettura e scrittura di titolo, autore, soggetto, parole chiave, creatore
- **PDF → Images**: esportazione pagine in PNG, JPEG, TIFF con DPI configurabile
- **Images → PDF**: conversione immagini (PNG, JPG, TIFF, BMP) in PDF multipagina
- **Batch mode**: elaborazione parallela su più file (ThreadPoolExecutor, max 4 worker); callback progresso via `pyqtSignal`
- **Recent files**: lista degli ultimi 10 file aperti in `~/.pdfusion/recent.json`
- **PDF Viewer**: visualizzazione pagine con zoom, navigazione frecce/tastiera, barra navigazione
- **Thumbnail panel**: striscia thumbnail lazy (rendering solo viewport visibile su QThread dedicato); drag-and-drop per riordinare
- **Sidebar strumenti**: lista navigabile di tutti i 16 strumenti disponibili
- **Pannelli strumenti**: un pannello dedicato per ogni strumento, con form opzioni + checkbox "Salva come nuovo file" + pulsante Applica
- **Tema UI**: palette warm off-white (#F5F4F1), accent slate-blue (#4A6FA5), font Noto Sans; QSS globale
- **Scrittura atomica**: `TempManager.atomic_write()` — scrittura su temp, poi `os.replace()`; intercetta `PermissionError` su Windows
- **Parser range pagine**: `parse_page_ranges("1-3, 5, last")` con validazione, supporto keyword `last`, deduplicazione e ordinamento
- **Installer Windows**: NSIS con Start Menu, collegamento Desktop opzionale, associazione file .pdf, uninstaller registrato
- **AppImage Linux**: script `build_appimage.sh`, `.desktop` entry, `AppRun`
- **DMG macOS**: script `create_dmg.sh` con `create-dmg`, firma condizionale via `sign.sh`
- **GitHub Actions**: `ci.yml` (lint + test su ubuntu + windows), `build-develop.yml` (pre-release su tag `v*-beta*`), `build-release.yml` (release stabile su `v*.*.*`)
- **PyInstaller spec**: bundle ottimizzato, esclude Qt3D / QtWebEngine / QtMultimedia → target < 80 MB
- **Test suite**: ~70 test su tutti i moduli core con fixture PDF autogenerati

[Unreleased]: https://github.com/0verwrite/PDFusion/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/0verwrite/PDFusion/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/0verwrite/PDFusion/releases/tag/v0.1.0
