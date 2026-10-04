# Changelog

All notable changes to PDFusion are documented in this file.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`

For planned features, see [ROADMAP.md](ROADMAP.md).

---

## [Unreleased]

### Added

- **Opt-out for the automatic update check**: a checkable **? → Controlla aggiornamenti all'avvio** menu
  entry (on by default) turns the silent startup check off. The choice is persisted in
  `~/.pdfusion/update_check.json` next to the throttle and "skip this version" state. The on-demand
  **? → Controlla aggiornamenti…** check is unaffected.

### Changed

- **Dependencies**: pikepdf 10.13.0.post1 → 10.14.0 via #94; ruff 0.16.8 → 0.16.9 (dev-only) via #95.
- **macOS minimum version**: pikepdf 10.14.0 only ships macOS wheels for macOS 15+ on Apple Silicon
  (10.13 needed macOS 14+ on arm64). The macOS installer is built on an arm64 runner, so it was already
  Apple-Silicon-only; its minimum macOS is now **15** (it was 14, never the "11+" the README stated).
  The test suite and CI cannot exercise the DMG on macOS, so only the build is verified.

### Removed

- **`pydantic-settings`** (and, with it, `pydantic`, `pydantic-core`, `python-dotenv`, `typing-inspection`)
  from `requirements.txt` via #97. It was never imported anywhere in `src/` or `tests/`, so nothing
  changes for the application: a PyInstaller build without it has the same size and contents.

### Fixed

- **Compression crashed on any PDF with a high-resolution image**: `compress` called
  `Document.replace_image`, which does not exist in PyMuPDF (only `Page.replace_image` does), and the
  surrounding `except` only caught `OSError`/`ValueError`, so every PDF containing an image above the
  target DPI failed with `AttributeError`. It went unnoticed because the test fixtures only have small
  images, which are skipped before that line. Now uses `Page.replace_image` (it replaces the image
  object by xref, so it applies to every page using it) and `Image.Resampling.LANCZOS`. A 26 MB PDF with a
  3000×3000 px image goes down to 0.5 MB (eBook preset) / 50 KB (screen preset). Found by `mypy`.
- **Update check never offered the beta → stable promotion**: the beta channel only looked at
  pre-releases, so a user on `0.3.0-beta3` was never told about `v0.3.0`, although `is_newer()` and the
  0.3.0 notes describe exactly that case. The beta channel now considers pre-releases and stable
  releases (the stable channel still only stable ones; drafts are always skipped), and the release is
  chosen by version instead of by the order GitHub lists them, so a hotfix published later on an older
  line cannot hide a newer beta.
- **`MainWindow.shutdown()` was not idempotent** via #99: its first step, `self.destroyed.disconnect()`,
  raises `TypeError` (not `RuntimeError`) in PyQt6 when the signal has no connections, so a second call
  on the same window logged an error and skipped every remaining step. The first call, including the
  real app close, was not affected; the second one happens in the tests and filled their logs with
  errors that could hide real ones.

### Testing

- `utils/update_checker.py` had no tests; added 64 (tag parsing, `is_newer`, installer choice per OS, the
  24h throttle, skipped tag, opt-out, `fetch_latest_release` against a fake `urlopen` including the
  request itself) plus 8 UI tests for the new menu entry. They never touch the network or the real
  `~/.pdfusion` folder.
- `MainWindow.shutdown()` had no tests; added 4 (no error logged, every step runs in order, an open
  document is closed and temp files are removed, calling it twice is clean).
- The two failure branches of `_close_worker()` in the viewer and in the thumbnail panel — `invokeMethod`
  raising (main-thread fallback) and the worker never acknowledging within 2 s — had no tests; added 4,
  using a real running `QThread` parented to the widget and a document opened on the main thread, so
  they cannot trigger the cross-thread finalisation that aborts on Linux.
- `compress` had no test with an image above the target DPI; added 4 (RGB and RGBA are downsampled and the
  output stays a valid, renderable PDF; a lower preset gives a smaller image; flattening iterates every page).
- Suite: 373 → 457 tests.

### Documentation

- README: macOS requirement corrected; new "Release Channels & Updates" section (beta vs stable, the
  in-app update check and what it sends); technology stack table updated to the pinned versions.
- CONTRIBUTING: documents the branch/release flow and the changelog convention.
- README and CONTRIBUTING no longer tell contributors to run `ruff format` or `isort`, and `mypy` is
  described as informational. CI only enforces `ruff check src/ tests/`; `isort` orders imports
  differently from ruff's `I` rules (following the old advice produced lint errors CI rejects),
  `ruff format` would rewrite 34 files, and `mypy` currently reports errors (87 with the project
  configuration), so the old checklists could not be satisfied.

---

## [0.3.0] — 2026-09-27

> This cycle was first published as the pre-releases `v0.2.11-beta1` and `v0.2.11-beta2`.
> Because it drops support for Python 3.11 and 3.12 (a breaking change), the release was
> renumbered to **0.3.0** and its pre-releases restarted at `v0.3.0-beta1`, followed by
> `v0.3.0-beta2` and `v0.3.0-beta3` before this stable promotion.

### Added

- **In-app update check**: PDFusion now checks GitHub Releases for a newer version, silently
  at startup (throttled to once per 24h) and on demand via **? → Controlla aggiornamenti…**.
  The check follows the running build's channel — a beta build compares against pre-releases,
  a stable build only against stable releases — and treats a same-version beta→stable
  promotion as an available update. When a newer release is found, a dialog shows its release
  notes with **Scarica** (opens the matching installer asset for the current OS directly in
  the system browser — PDFusion never downloads or executes anything itself), **Ignora questa
  versione**, and **Più tardi**. Implemented as a pure-Python `utils/update_checker.py` (stdlib
  `urllib`, no new dependency) plus a `QThread` worker in `ui/main_window.py`, following the
  same worker pattern as `base_panel._Worker`.
- **Version now shows its channel**: a new `VERSION_SUFFIX` constant in `config.py` (e.g.
  `"-beta3"`, empty for a stable release) is combined into `FULL_VERSION`, shown in the window
  title and the About dialog instead of the bare `VERSION`. `VERSION_SUFFIX` is updated by hand
  together with `VERSION` as part of the existing versioning workflow, and cleared on stable
  promotion.
- **About dialog**: now shows a clickable link to the GitHub repository.

### Removed

- **BREAKING — Python 3.11 and 3.12 are no longer supported.** PDFusion now requires Python 3.13
  (`requires-python = ">=3.13,<3.14"`). The CI matrix is reduced to 3.13, ruff targets `py313`,
  mypy targets 3.13, and the release/pre-release builds now bundle a 3.13 interpreter (they used
  3.12 before). `start.sh` / `start.bat` only accept 3.13, and README, CONTRIBUTING and
  `requirements.txt` are updated. End users of the installers are not affected by the version of
  a system Python, but the bundled interpreter changes from 3.12 to 3.13.

### Changed

- **PyMuPDF import**: all code and tests now use `import pymupdf` instead of the deprecated
  `import fitz` (13 modules in `src/`, 3 test files). PyMuPDF 1.28.2 printed a deprecation warning
  for `fitz` at startup; it no longer appears, including in the frozen executable.
- **Dependencies**: routine updates
  - Runtime: PyMuPDF 1.28.0 → 1.28.2, pikepdf 10.10.0 → 10.12.0 → 10.13.0.post1, reportlab
    5.0.0 → 5.0.1, pydantic-settings 2.14.2 → 2.15.0 (MINOR/PATCH) via #89 and #91. Note:
    `pydantic-settings` is not imported anywhere in `src/` or `tests/`, so that bump is not
    exercised by the test suite
  - Dev-only: ruff 0.16.0 → 0.16.1 → 0.16.3 → 0.16.8 and pyinstaller 6.21.0 → 6.22.0 → 6.22.3
    via #85, #87, #92
  - Dependabot version-update PRs (pip + github-actions) now open monthly instead of weekly;
    security updates are unaffected and still open in real time
- **Typing**: `Generator[Path, None, None]` → `Generator[Path]` (ruff `UP043`, valid from 3.13)
- **Project automation**: `project-automation.yml` now auto-labels Issues too (previously only
  Dependabot PRs and manually opened PRs were labeled; Issues never received any label from
  automation). Same title-prefix heuristic style: `bug:`/`[Bug]`→`type:bug`, `feat:`/`[Feature]`→
  `type:feature`, `docs:`/`[Docs]`→`type:docs`, `question:`/`[Question]`→`question`,
  default→`type:chore`

### Fixed

- **Viewer and thumbnail workers never closed their PDF on the worker thread.**
  `_close_worker()` (in `ui/viewer.py` and `ui/thumbnail_panel.py`) tested the return value of
  `QMetaObject.invokeMethod()`. In PyQt6 that call returns `None` on success and raises
  `RuntimeError` on failure, so the check (`if not invoked`) was always true: every close logged
  a bogus "invokeMethod returned False" warning, skipped the bounded wait for the worker's
  acknowledgement and closed the document on the main thread instead, racing with a still-queued
  `render()`. The check is removed; the existing `except` already handles a real failure.
  This is the root cause of the intermittent failures of
  `test_close_worker_sets_worker_to_none_first` and
  `test_thumb_worker_snapshot_prevents_use_after_free` (the latter also failed once in CI on
  Ubuntu / Python 3.13 during the 0.2.9 release). Regression tests were added for both classes;
  on the old code they fail every time.
- The earlier attempt to fix that flake by waiting for the `rendered` signal in the test was based
  on a wrong diagnosis and is reverted: the test is back to its original form, now deterministic.
- **Metadata**: writing `author` set `dc:creator` in the XMP metadata as a plain string. Per the
  XMP spec `dc:creator` is an ordered array (`rdf:Seq`); pikepdf >= 10.13.0 (bumped via #91) warns
  (`XmpTypeWarning`) when it is assigned a `str` instead of a list. Fixed by wrapping it in a
  single-element list. `docinfo /Author` — what `read_metadata`/`PDFMetadata.author` actually
  reads back — is unaffected, still a plain string.
- **QSpinBox/QDoubleSpinBox up/down arrows rendered blank in compiled builds** (reported against
  `v0.3.0-beta2`, visible in every panel with a spin box, e.g. "Modalità di divisione"). Same root
  cause as the v0.2.6→v0.2.7 blank-icon bug: `styles/theme.py` recomputed the icons directory from
  `Path(__file__).parent.parent.parent` instead of importing `ICONS_DIR` from `utils.config` — in a
  frozen PyInstaller build this points outside `_MEIPASS`/`_internal/assets`, so the arrow SVGs
  never loaded. Never reproduced in dev mode, only in the packaged installer. Fixed by importing
  `ICONS_DIR` from `utils.config` instead of recomputing it.

### Testing

- Full suite: 373/373 (372/372 in 10 consecutive full runs after the worker-close fix, plus one
  new metadata regression test); `ruff check src/ tests/` clean
- A real local PyInstaller build on Python 3.13 (6.22.0, then 6.22.3 via #92) succeeds and the
  frozen executable starts headless; the pymupdf migration was verified there too, since pytest
  does not exercise packaging
- **Fixed a long-standing flaky memory test**: `test_below_threshold_uses_simple` (in
  `tests/test_merge_chunked.py`) asserted on the *absolute* process RSS (`psutil`), which
  accumulates monotonically over an entire pytest session (373 tests share one process) and so
  depends on execution order rather than on `merge()` itself — it always passed in isolation but
  occasionally failed in the full suite. `memory_tracker` now tracks a `delta_mb` (peak − baseline,
  baseline taken immediately before the operation under test) and the assertion checks that delta
  instead. Verified with 3 consecutive full-suite runs (373/373) after the fix.
- Added a startup-time regression guard: `ui/main_window.py`'s automatic update check is disabled
  when `PYTEST_CURRENT_TEST` is set, so instantiating `MainWindow()` in tests never makes a real
  network request from a background thread (it did before this guard was added, and crashed the
  test process during teardown — the same class of thread-lifecycle risk documented for the
  fitz worker-close bugs above).

---

## [0.2.10] — 2026-08-01

### Changed

- **Dependencies**: Routine dependency updates
  - GitHub Actions: `actions/setup-python` v6 → v7 (ESM migration, pinned SHA commits) via #81
  - ruff: 0.15.21 → 0.15.22 (PATCH — dev-only) via #82
  - ruff: 0.15.22 → 0.16.0 (MINOR — dev-only) via #83. Despite the version jump, no rule-set
    regression: the project pins an explicit `[tool.ruff.lint] select` list, so ruff's much
    larger default rule set (413 vs. 59) does not affect `ruff check src/ tests/` as run in CI
- **Release process**: Formalized the beta (develop) → stable (main) release workflow
  - `build-develop.yml` now pulls its pre-release notes from the CHANGELOG `[Unreleased]`
    section, mirroring how `build-release.yml` already pulled from the versioned section
  - GitHub release note templates (both workflows) translated from Italian to English
  - `project-automation.yml`: added a heuristic that auto-labels manually opened PRs
    (`type:*` from the conventional-commit title prefix, `scope:core`/`scope:frontend`/
    `type:ci`/`dependencies`/`lang:python` from changed files) — Dependabot PRs were already
    labeled via `dependabot.yml`, but manual PRs never received any label until now
  - `project-automation.yml`: dropped the automatic reviewer request, redundant now that
    `main`'s branch ruleset requires 0 approving reviews (single-developer project)
  - Repo setting `delete_branch_on_merge` enabled — temporary/Dependabot branches are now
    deleted automatically on merge

### Testing

- 370/370 tests pass locally after all dependency updates (ruff 0.16.0 run explicitly
  verified: lint clean, full suite green — no flaky failures this run)

---

## [0.2.9] — 2026-07-13

### Changed

- **Dependencies**: Routine dependency updates
  - pikepdf: 10.9.1 → 10.10.0 (PATCH via #78)
  - ruff: 0.15.20 → 0.15.21 (PATCH via #79)

### Testing

- 369/370 tests pass locally after both updates
- 1 pre-existing flaky test (`test_below_threshold_uses_simple` — memory-threshold timing, unrelated to dependency updates)
- Ubuntu py3.13 CI showed a one-off thread-safety timing flake (`test_thumb_worker_snapshot_prevents_use_after_free`) on first run; confirmed as pre-existing CI flakiness (not caused by the pikepdf bump) via a clean rerun

---

## [0.2.8] — 2026-07-08

### Fixed

- **CRITICAL**: Windows installer setup.exe and application window showing blank white icon instead of PDFusion icon
  - Root cause #1 (setup.exe): `installer/windows/installer.nsi` had `MUI_ICON`/`MUI_UNICON` defines declared **after** `!include "MUI2.nsh"`. MUI2.nsh applies the icon during include time; if define doesn't exist yet, falls back to blank. Moved defines before include.
  - Root cause #2 (running app): `src/main.py` never called `app.setWindowIcon()`. Without this, Qt doesn't assign icon to titlebar/taskbar/Alt-Tab regardless of how exe is compiled. Added call with icon path existence check.
  - Root cause #3 (frozen builds): `src/utils/config.py` calculated `ASSETS_DIR` incorrectly in PyInstaller frozen builds. `__file__` in frozen code is synthetic path inside `sys._MEIPASS`; ascending 3 parents went **above** `_MEIPASS` instead of staying inside. Asset paths fell back silently (QIcon failed, templates not found). Added `sys.frozen` bifurcation to use `sys._MEIPASS` in compiled builds, `__file__`-based path in dev.
  - All three bugs were independent and each needed fixing — any one alone leaves icon missing in either setup.exe or running application.

---

## [0.2.7] — 2026-07-07

### Fixed

- **Bug fix**: Windows installer shortcuts now display correct icon instead of blank white square
  - Root cause: PyInstaller 6.x places bundled datas under `_internal/` subdirectory. Previous attempt to reference icon file at `$INSTDIR\assets\icons\app.ico` failed because actual path was `$INSTDIR\_internal\assets\icons\app.ico`
  - Solution: Use icon embedded in PDFusion.exe itself (incorporated by PyInstaller via icon= in spec) instead of separate file reference
  - Benefit: More robust — does not depend on PyInstaller's internal path layout, and icon is guaranteed to always exist
  - Files: `installer/windows/installer.nsi` (define APP_ICON as `$INSTDIR\${APP_EXE}`, update CreateShortcut calls for Start menu and Desktop)

- **CRITICAL**: Fix threading deadlock on Windows + Python 3.11 AND SIGABRT on Ubuntu + Python 3.13
  - Dual-constraint problem: Windows deadlock required non-blocking + timeout, Ubuntu SIGABRT required guaranteed fitz-close-on-worker-thread
  - Root cause: Previous `BlockingQueuedConnection` blocked main thread indefinitely (Windows race); `QueuedConnection` failed to guarantee fitz closes before thread exits (Ubuntu SIGABRT)
  - Definitive solution: Use `QWaitCondition` with bounded timeout (2s) and predicate guard to guarantee both fitz-on-worker AND bounded main-thread wait
  - Implementation:
    * `_close_doc_sync()` closes fitz on worker thread, sets flag, calls wakeAll() on condition variable (all under mutex)
    * `_close_worker()` resets flag, queues `_close_doc_sync` via `QueuedConnection`, acquires mutex, waits with 2s timeout and predicate check
    * Predicate guard prevents lost-wakeup race if worker closes before main reaches wait()
  - Benefit: Eliminates unbounded wait while guaranteeing fitz closed on worker (prevents both deadlock and SIGABRT)
  - Files: `src/ui/viewer.py`, `src/ui/thumbnail_panel.py` (_close_worker and worker class methods)

---

## [0.2.6] — 2026-06-22

### Fixed

- **Security**: Update pydantic-settings to 2.14.2 to fix symlink traversal vulnerability (GHSA-4xgf-cpjx-pc3j)
  - Prevent NestedSecretsSettingsSource from following symlinks outside secrets_dir
  - Affected versions: pydantic-settings >= 2.12.0, < 2.14.2
  - Update: 2.14.1 → 2.14.2 (PATCH version bump)

- **Bug fix**: Update pikepdf to 10.9.1 to prevent SIGABRT during exception unwinding
  - Fixed crash when file-backed Pdf objects deallocated during exception propagation
  - Update: 10.8.0 → 10.9.1 (PATCH version bump)

### Changed

- **Dependencies**: Comprehensive stability and compatibility updates
  - pytest: 9.0.3 → 9.1.1 (PATCH - bug fixes)
  - ruff: 0.15.17 → 0.15.20 (PATCH - improvements & bug fixes via #68)
  - reportlab: 4.5.1 → 5.0.0 (MAJOR - fully backward-compatible, 369/370 tests pass)
  - GitHub Actions: actions/checkout v6 → v7 (ESM upgrade, Node.js 24 support)

### Testing

- All 369/370 tests pass with updated dependencies
- 1 pre-existing flaky test (test_below_threshold_uses_simple - timing-dependent, unrelated to dependency updates)
- reportlab 5.0.0 compatibility verified through comprehensive test suite

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
