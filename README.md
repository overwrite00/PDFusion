# PDFusion

A powerful, open-source desktop application for PDF manipulation built with PyQt6.

## ✨ Features

- 📄 **Merge** — Combine multiple PDFs into one
- ✂️ **Split** — Divide PDFs by page ranges or individual files
- 🔄 **Reorder** — Rearrange pages with intuitive controls
- 🎨 **Watermark** — Add text or images (7 positions, custom opacity/rotation)
- 🔒 **Protect** — Password encryption (AES-128/256) with permission restrictions
- 📸 **Convert** — PDF↔Images (PNG/JPG/TIFF), image collections→PDF
- 📋 **Extract & Delete** — Work with specific page ranges
- 📝 **Headers & Footers** — Add custom text with dynamic variables
- 📃 **License Pages** — Insert branded license pages (11+ templates)
- 🗜️ **Compress** — Reduce file size with quality presets (Screen/eBook/Print/Prepress)
- 📊 **Metadata** — Edit PDF title, author, subject, and other properties
- 🔄 **Batch Processing** — Process multiple files in parallel
- 🎯 **Rotate** — Rotate pages 90°/180°/270°
- 📅 **Dynamic Variables** — Auto-fill {page}, {total}, {date}, {title}, {author}

## 🖥️ System Requirements

- **Python**: 3.11–3.13
- **OS**: Windows 10+, macOS 11+, Linux (Debian/Ubuntu/Fedora)
- **RAM**: 2 GB minimum, 4 GB recommended

## 📦 Installation

### From Source

```bash
# Clone repository
git clone https://github.com/[your-username]/PDFusion.git
cd PDFusion

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python src/main.py
```

### Pre-built Installers

Pre-built executables available in [Releases](https://github.com/[your-username]/PDFusion/releases):

- **Windows**: `PDFusion-0.1.0-windows-setup.exe` (NSIS installer)
- **macOS**: `PDFusion-0.1.0-macos.dmg` (disk image)
- **Linux**: `PDFusion-0.1.0-linux.AppImage` (portable)

## 🚀 Quick Start

1. **Open PDFusion** — Launch the application
2. **Load PDF** — Use File menu or drag-and-drop to load your PDF
3. **Select Tool** — Click a tool from the left sidebar
4. **Configure** — Adjust settings in the right panel
5. **Apply** — Click **Apply** to preview, or **Apply and Save As** to save

### Example Workflows

**Split PDF by ranges**:
1. Open PDF → Select "Split" tool
2. Enter ranges: `1-5, 10-15, 20`
3. Click "Apply and Save As"
4. Choose output directory

**Add watermark**:
1. Open PDF → Select "Watermark" tool
2. Choose text or image mode
3. Select position (e.g., CENTER_DIAGONAL)
4. Adjust opacity/rotation
5. Click "Apply" to preview, then save

**Protect with password**:
1. Open PDF → Select "Protect" tool
2. Enter user password (required to open)
3. Optionally set owner password (restrict printing/copying)
4. Choose encryption: AES-128 (default) or AES-256
5. Click "Apply and Save As"

## 🔧 Development

### Setup Development Environment

```bash
pip install -r requirements-dev.txt
```

### Run Tests

```bash
# Using pytest directly
pytest tests/ -v

# Or using scripts
./run_tests.sh       # Linux/macOS
run_tests.bat        # Windows
```

### Build Standalone Executable

```bash
pyinstaller PDFusion.spec --noconfirm
# Output: dist/PDFusion/ (executable + dependencies)
```

### Project Structure

```
PDFusion/
├── src/
│   ├── main.py                 # Application entry point
│   ├── core/                   # PDF manipulation logic (PyMuPDF, pikepdf)
│   │   ├── split.py, merge.py, compress.py, protect.py, watermark.py
│   │   ├── headers_footers.py, license_page.py, rotate.py, reorder.py
│   │   ├── extract_pages.py, delete_page.py, insert_page.py
│   │   ├── metadata.py, pdf_to_images.py, images_to_pdf.py, batch.py
│   │   └── ...
│   ├── ui/                     # PyQt6 GUI components
│   │   ├── main_window.py      # Main window
│   │   ├── viewer.py           # PDF viewer with zoom/navigation
│   │   ├── thumbnail_panel.py  # Page thumbnails
│   │   ├── sidebar.py          # Tool selection
│   │   ├── panels/             # Tool-specific UI panels
│   │   ├── dialogs/            # Dialogs (about, password, progress)
│   │   └── widgets/            # Reusable components
│   ├── utils/
│   │   ├── config.py           # Configuration & versioning
│   │   ├── temp_manager.py     # Temporary file management
│   │   ├── page_range_parser.py # Page range parsing ("1-3,5,7-9")
│   │   ├── recent_files.py     # Recent files tracking
│   │   └── exceptions.py
│   └── styles/
│       ├── theme.py            # Color palette & theme
│       └── pdfusion.qss        # Qt stylesheet
├── tests/                      # Test suite
│   ├── core/                   # Core module tests
│   ├── fixtures/               # Test PDFs
│   └── utils/                  # Utility tests
├── installer/                  # Multi-platform installers
│   ├── windows/                # NSIS installer config
│   ├── linux/                  # AppImage builder
│   └── macos/                  # DMG creator + signing scripts
├── assets/                     # Resources
│   ├── icons/                  # Application icons
│   ├── fonts/                  # Bundled fonts
│   └── licenses/templates/     # License page templates
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # Development dependencies
├── pyproject.toml              # Project configuration
├── PDFusion.spec               # PyInstaller configuration
├── CHANGELOG.md                # Version history
└── README.md                   # This file
```

## 📊 Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| GUI | PyQt6 | 6.9.0+ |
| PDF Rendering | PyMuPDF (fitz) | 1.25.5+ |
| PDF Manipulation | pikepdf | 9.7.0+ |
| PDF Generation | ReportLab | 4.4.1+ |
| Image Processing | Pillow | 11.0.0+ |
| Template Engine | Jinja2 | 3.1.0+ |
| Packaging | PyInstaller | 6.13.0+ |
| Testing | pytest, pytest-qt | 8.3.5+ |

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to your branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request targeting `develop` branch

### Code Style

- Follow PEP 8 style guidelines
- Use type hints where applicable
- Write docstrings for public methods
- Keep functions focused and testable

### Before Submitting PR

- Run tests: `pytest tests/`
- Check code style: `ruff check src/`
- Format code: `ruff format src/`

## 📋 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history and upcoming features.

## 🔗 Links

- **GitHub**: [github.com/[your-username]/PDFusion](https://github.com/[your-username]/PDFusion)
- **Issues**: [Report bugs or request features](https://github.com/[your-username]/PDFusion/issues)
- **Releases**: [Download installers](https://github.com/[your-username]/PDFusion/releases)

## 💡 Tips & Tricks

- **Keyboard Navigation**: Use arrow keys in the page navigation bar
- **Drag & Drop**: Drop PDFs directly into the application window
- **Recent Files**: Quick-access menu shows last 10 opened files
- **Batch Mode**: Process multiple PDFs in one operation
- **Custom Headers/Footers**: Use variables like `{page}`, `{total}`, `{date}` for dynamic content

## ⚠️ Known Limitations

- **SVG Watermarks**: Basic SVG support only (complex paths may not render)
- **Large Files**: Documents with 500+ pages may require more processing time
- **Password-Protected PDFs**: User must enter password to open

## 🐛 Troubleshooting

**Q**: Application won't start
**A**: Ensure Python 3.11+ is installed. Run `python --version` to verify.

**Q**: "Module not found" error
**A**: Reinstall dependencies: `pip install -r requirements.txt`

**Q**: PDF viewer is blank
**A**: Try opening a different PDF. Some files may have rendering issues.

**Q**: Changes don't appear in output
**A**: Ensure you click "Apply and Save As" (not just "Apply" for preview)

---

**Version**: 0.1.0 | **Last Updated**: 2025-01-01

Made with ❤️ by PDFusion contributors
