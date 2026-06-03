# Changelog

All notable changes to PDFusion are documented in this file.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`

For planned features, see [ROADMAP.md](ROADMAP.md).

---

## [Unreleased]

### Added

- Planned features and improvements for future releases.

---

## [0.2.0] — 2026-06-03

### Security

- Fixed race condition in main_window._on_operation_done() after _cleanup_all_temps() — added file existence guard
- Fixed thread timeout vulnerability in base_panel worker cleanup — snapshot pattern + fallback terminate()
- Fixed thread-unsafe document closure in viewer.py and thumbnail_panel.py using reference snapshot pattern
- Fixed silent password failures in batch operations — explicit error raising instead of silent fallback

### Fixed

- **CRITICAL #1**: Resource leak in compress.py, pdf_to_images.py, headers_footers.py — nested try-finally
- **CRITICAL #9**: Thread-unsafe worker cleanup (viewer, thumbnail_panel) — snapshot pattern for safe reference
- **CRITICAL #11**: Per-file passwords in batch — added password_map for per-file password resolution
- **HIGH #10**: Large PDF memory spike — binary tree chunked merge (O(sqrt(n)) instead of O(n))
- **HIGH #12**: PIL Image and reportlab Canvas resource leaks — context managers and explicit cleanup
- **HIGH #13**: Font registry pollution in batch operations — singleton FontManager with idempotent registration
- **HIGH #14**: ThreadPoolExecutor hanging — timeout handling (30s) with exponential backoff retry
- **HIGH #15**: Silent page range failures — validation before operations + detailed logging
- **BUG #1**: Encrypted PDF handling in compress.py — added doc.authenticate() before saving protected documents
- **BUG #2**: Batch watermark operations with None config — provide default WatermarkConfig when not specified
- **BUG #3**: Test fixture password handling — corrected ProtectConfig usage in test_batch_passwords.py

### Added

- **New Utility**: `src/core/pdf_opener.py` — centralized PDF opening with password+format error handling
- **New Utility**: `src/utils/font_manager.py` — singleton FontManager preventing duplicate registrations
- **New Utility**: `src/utils/page_validator.py` — page range validation with helpful error messages
- **New UI Components**: FileMonitorManager, PreviewRenderer for SOLID refactoring
- **Testing**: 180+ new test cases across 12 test suites (Week 1-3 coverage)
  - Resource cleanup tests (29 cases)
  - Thread safety tests (35+ cases)
  - Batch password tests (20+ cases)
  - PDF opener tests (19 cases)
  - Font manager tests (21 cases)
  - Merge chunked tests (19 cases)
  - Resource manager tests (18 cases)
  - Executor timeout tests (21 cases)
  - Page validation tests (56 cases)
  - Base panel refactor tests (58 cases)
- **Documentation**: CONTRIBUTING.md with dev setup, PR workflow, testing guidelines

### Changed

- **Refactor**: BasePanelWidget SOLID refactoring — extracted FileMonitorManager, PreviewRenderer (REFACTOR #17)
- **DRY**: Consolidated 18 duplicate pikepdf.open() calls into pdf_opener.py helper (REFACTOR #16)
- **Code Quality**: Enhanced exception handling across all core modules (specific > generic)
- **Logging**: Comprehensive logging for batch operations, timeouts, retries
- **API**: No breaking changes — all modifications are backward compatible

---

## [0.1.0] — 2026-04-27

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
