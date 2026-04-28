# Changelog

All notable changes to PDFusion are documented in this file.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`

---

## [Unreleased]

_Prossime funzionalità pianificate:_

- Drag-and-drop dal file manager verso la sidebar strumenti
- Anteprima watermark in tempo reale nel viewer
- Esportazione report operazioni in CSV
- Integrazione firma digitale (PKCS#7 / PAdES)
- Supporto PDF/A (validazione e conversione)
- Temi UI aggiuntivi (dark mode)
- Localizzazione italiano/inglese (i18n)
- Plugin architecture per estensioni di terze parti

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

[Unreleased]: https://github.com/0verwrite/PDFusion/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/0verwrite/PDFusion/releases/tag/v0.1.0
