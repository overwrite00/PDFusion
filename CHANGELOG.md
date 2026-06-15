# Changelog

All notable changes to PDFusion are documented in this file.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`

For planned features, see [ROADMAP.md](ROADMAP.md).

---

## [Unreleased]

(No unreleased changes at this time.)

---

## [0.2.5] — 2026-06-15

### Fixed

- **Security**: Update pytest to 9.0.3 to fix tmpdir vulnerability (CVE-2025-71176)
  - Resolves Dependabot alerts #1 and #4 (pytest tmpdir handling vulnerability)
  - Affected versions: pytest < 9.0.3
  - Update: 8.4.2 → 9.0.3 (MAJOR version bump)
  - Testing: 369/370 tests pass; 1 pre-existing flaky timing test unrelated to pytest
  - Impact: Reduces default branch vulnerabilities from 8 → 6

---

## [0.2.2] — 2026-06-05

### Fixed

- **CRITICAL**: Ubuntu CI SIGABRT (exit 134) at 72% during pytest teardown
  - Root cause: Two autouse fixtures with conflicting LIFO teardown order caused `gc.collect()` to
    run AFTER `_flush_qt_deletions`, finalizing still-running QThread objects. On Linux's offscreen
    plugin, thread-join timing is racy — threads could still look "running" when GC finalized them,
    triggering Qt's `~QThread()` → `qFatal()` → `abort()` → SIGABRT.
  - Why Windows never crashed: `QThread::wait()` synchronously clears `d->running` before returning.
    Offscreen plugin has looser join semantics, leaving a race window.
  - Fix (two parts):
    1. **_flush_qt_deletions fixture**: Use `sip.delete(thread)` immediately after confirming thread
       stopped, instead of relying on `deleteLater()` → deferred GC. Prevents `~QThread()` from ever
       executing on a live thread.
    2. **test_close_worker_exception_logging**: Deterministically clean up orphan thread AFTER mock
       removed, ensuring _flush_qt_deletions finds it already stopped and can delete it immediately.
  - Result: All 1,110+ tests pass on Ubuntu (3.11/3.12/3.13) and Windows with zero crashes.

### Changed

- **tests/test_thread_safety.py**:
  - `_flush_qt_deletions`: Import sip at top of fixture; call `sip.delete(thread)` immediately
    after `_stop_thread()` confirms stopped (widget threads and backstop orphans).
  - `test_close_worker_exception_logging`: Add explicit `thread.quit()`/`thread.wait()` after
    mock context to ensure orphan thread is stopped before fixture teardown.
- **.github/workflows/ci.yml**:
  - Re-enable `ubuntu-latest` in test matrix (was disabled as temporary workaround).

---

## [0.2.1] — 2026-06-04

### Fixed

- **CRITICAL**: pthread_cancel deadlock on Linux/macOS when closing viewer/thumbnail threads blocked in fitz.get_pixmap()
  - Never use terminate() on Linux/macOS (pthread_cancel remains pending in non-cancel-safe C code, causing permanent deadlock)
  - Changed to quit() + polling wait(100ms) pattern on Unix, with Windows fallback to terminate()
- **CRITICAL**: Test-production contract misalignment causing SIGABRT in _flush_qt_deletions fixture
  - Thread-safety tests now platform-aware: assert no terminate() on Linux/macOS, terminate() fallback on Windows
  - Production _shutdown_thread hardened with separate try blocks for quit() and wait() — ensures wait() runs even if quit() fails
- Ubuntu CI now passes all 370 tests reliably without hangs

### Changed

- Thread lifecycle management in src/ui/viewer.py, src/ui/thumbnail_panel.py, src/ui/panels/preview_renderer.py
  - Production: split quit()/wait() into separate exception handlers
  - Tests: capture and reuse real wait() implementation before mocking, ensuring threads are genuinely stopped

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
