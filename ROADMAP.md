# PDFusion Roadmap

This document outlines planned features and improvements for PDFusion. Features are organized by priority and estimated timeline.

---

## 🎯 Next Release (v0.3.0) — Q3 2026

### UI/UX Enhancements

- [ ] **Real-time watermark preview** in viewer while configuring watermark options
- [ ] **Drag-and-drop support** from file manager directly to tool panels in sidebar
- [ ] **Dark mode** theme with automatic system preference detection
- [ ] **Keyboard shortcuts panel** with customizable bindings

### Testing & Quality

- [ ] Increase UI test coverage to 70%+
- [ ] Add integration tests for multi-step workflows (e.g., watermark → compress → protect)
- [ ] Performance benchmarking suite for large PDFs (100+ MB)

---

## 🚀 Future Releases (v0.4.0+) — Q4 2026 and Beyond

### Document Security

- [ ] **Digital signature support** (PKCS#7 / PAdES standard)
  - Sign PDFs with X.509 certificates
  - Signature verification UI
- [ ] **PDF/A support** (archival-grade format)
  - Validate PDF/A compliance
  - Convert PDF to PDF/A-1b or PDF/A-2b
- [ ] **Advanced permissions** (content extraction, form field editing, etc.)

### Content Management

- [ ] **CSV export reports** of batch processing results
- [ ] **Batch metadata templating** (apply same metadata to multiple PDFs)
- [ ] **Table of contents auto-generation** based on PDF structure
- [ ] **OCR integration** for scanned PDFs (Tesseract backend)

### Localization & Accessibility

- [ ] **Internationalization (i18n)**
  - Italian (100%, current)
  - English (100%, current)
  - German, French, Spanish, Portuguese (planned)
- [ ] **Accessibility improvements**
  - Screen reader support
  - High contrast mode
  - Keyboard-only navigation

### Developer Features

- [ ] **Plugin architecture** for custom PDF operations
  - Plugin SDK with example plugins
  - Plugin marketplace / registry
- [ ] **Command-line interface (CLI)** for headless operations
  - `pdfusion split --every 10 input.pdf`
  - `pdfusion merge file1.pdf file2.pdf -o output.pdf`
- [ ] **REST API** for embedding PDFusion operations in web services

### Performance & Infrastructure

- [ ] **GPU acceleration** for image processing (optional, CUDA/OpenCL)
- [ ] **Streaming mode** for processing PDFs larger than available RAM
- [ ] **Network support** (open files from SMB/NFS shares)
- [ ] **Cloud storage integration** (Google Drive, Dropbox, OneDrive)

---

## 📋 Known Limitations & TODOs

### Current Limitations

- No support for encrypted PDFs with owner password (read-only for protected content)
- Watermark text does not support Unicode/emoji properly
- Large PDFs (> 500 MB) may cause slowdowns in preview rendering
- No support for PDF forms (AcroForms, XFA)

### Improvement Areas

- [ ] Optimize memory usage for large batch operations
- [ ] Improve preview rendering performance with progressive loading
- [ ] Add undo/redo functionality in batch mode
- [ ] Support for PDF annotation editing (currently read-only)

---

## 🤝 Contributing

Want to help with any of these features? See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Setting up development environment
- Creating feature branches
- Submitting pull requests
- Code review process

---

## 📊 Release Schedule

| Version | Status | ETA |
|---------|--------|-----|
| [0.2.0](https://github.com/0verwrite/PDFusion/releases/tag/v0.2.0) | ✅ Released | 2026-05-27 |
| 0.3.0 | 🚧 Planning | Q3 2026 |
| 0.4.0 | 📋 Planned | Q4 2026 |
| 1.0.0 | 🎯 Goal | Q2 2027 |

---

## 💬 Feedback

Have ideas for features not listed?

- Open an [issue on GitHub](https://github.com/0verwrite/PDFusion/issues)
- Discuss in [GitHub Discussions](https://github.com/0verwrite/PDFusion/discussions)

---

Last updated: 2026-05-27
