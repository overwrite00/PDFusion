# Contributing to PDFusion

Thank you for your interest in contributing to PDFusion! This guide will help you set up your development environment and follow the correct workflow.

---

## 📋 Table of Contents

1. [Requirements](#requirements)
2. [Development Environment Setup](#development-environment-setup)
3. [PR Workflow](#pr-workflow)
4. [Code Style](#code-style)
5. [Testing](#testing)
6. [Commit Messages](#commit-messages)

---

## Requirements

- **Python**: 3.11, 3.12, or 3.13
- **Git**: Recent version
- **Operating System**: Windows 10+, macOS 11+, or Linux

---

## Development Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/overwrite00/PDFusion.git
cd PDFusion
```

### 2. Create a Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Runtime dependencies
pip install -r requirements.txt

# Development dependencies (testing, linting, type checking)
pip install -r requirements-dev.txt
```

### 4. Verify Setup

```bash
python -m pytest tests/ -v --tb=short
```

If all tests pass, your environment is ready! ✅

---

## PR Workflow

### 1. Create a Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/feature-name
```

**Naming convention:**

- `feature/` for new features
- `fix/` for bug fixes
- `refactor/` for refactoring
- `docs/` for documentation

### 2. Make Your Changes

```bash
# Modify files
# ...

# Run tests locally
python -m pytest tests/ -v

# Verify code style
python -m isort src/                # Organize imports
python -m ruff check src/           # Lint check
python -m ruff format src/          # Auto-format
```

### 3. Commit Your Changes

```bash
git add <file1> <file2> ...
git commit -m "fix: brief description of change"
```

**Commit Message Guidelines:**

- **Type**: `fix:`, `feat:`, `refactor:`, `docs:`, `test:`, `chore:`
- **Description**: imperative, lowercase
- **Length**: < 72 characters for first line
- **Body** (optional): detailed explanation after blank line

### 4. Push and Create PR

```bash
git push -u origin feature/feature-name
```

Then go to GitHub and create a Pull Request. Target base: `develop` (not `main`).

**PR Title Format:**

```
feat: Add support for digital signatures
```

**PR Description Template:**

```markdown
## 📝 Description

Brief description of changes.

## ✅ Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] Feature (non-breaking change that adds functionality)
- [ ] Breaking change (change that breaks compatibility)

## 🧪 Testing

Describe how you tested your changes:

- [ ] Unit tests written/updated
- [ ] Manual testing completed
- [ ] Coverage >= 80% for modified files

## 📋 Checklist

- [ ] Code style (ruff format, ruff check)
- [ ] Type hints (mypy --strict)
- [ ] Docstrings for new functions/classes
- [ ] CHANGELOG.md updated
```

---

## Code Style

### Linting with Ruff

```bash
# Verify style
python -m isort src/ tests/
python -m ruff check src/ tests/

# Auto-fix common issues
python -m ruff check --fix src/ tests/

# Formatting
python -m ruff format src/ tests/
```

**Configuration**: See `pyproject.toml` section `[tool.ruff]`

### Type Hints

Use type hints for:

- Function parameters
- Function return types
- Class attributes (when ambiguous)

**Example:**

```python
def process_pdf(
    input_path: Path,
    options: dict[str, Any] | None = None,
) -> Path:
    """Process a PDF with the provided options."""
    ...
```

### Docstrings

Use docstrings for:

- Public functions
- Classes
- Complex modules

**Format (Google-style):**

```python
def extract_pages(
    input_path: Path,
    ranges: list[tuple[int, int]],
    output_path: Path,
) -> Path:
    """
    Extract specific pages from a PDF.

    Args:
        input_path: Path to source PDF.
        ranges: List of tuples (start, end) 1-based.
        output_path: Path to output file.

    Returns:
        output_path after saving.

    Raises:
        PDFusionError: If file doesn't exist or is corrupted.
    """
    ...
```

---

## Testing

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test
python -m pytest tests/core/test_compress.py::TestCompress::test_screen_preset -v

# Batch password tests
python -m pytest tests/test_batch_passwords.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Writing Tests

1. **Unit tests** in `tests/core/test_*.py`
2. **UI tests** in `tests/ui/test_*.py`
3. **Fixtures** in `tests/fixtures/`

**Example Test:**

```python
def test_compress_with_screen_preset(tmp_path):
    """Verify compression with screen preset."""
    from core.compress import compress, CompressConfig, CompressPreset

    input_pdf = Path(__file__).parent / "fixtures" / "sample.pdf"
    output = tmp_path / "output.pdf"

    config = CompressConfig(preset=CompressPreset.SCREEN)
    result = compress(input_pdf, output, config)

    assert output.exists()
    assert output.stat().st_size < input_pdf.stat().st_size
```

**Example Test with Password-Protected PDF:**

```python
def test_compress_protected_pdf(tmp_path, sample_pdf):
    """Verify compression of password-protected PDF."""
    from core.protect import protect, ProtectConfig
    from core.compress import compress, CompressConfig, CompressPreset

    # IMPORTANT: Use ProtectConfig(user_password=...) to set output password
    protected_pdf = tmp_path / "protected.pdf"
    protect(sample_pdf, protected_pdf, ProtectConfig(user_password="test123"))

    # When calling compress(), provide password to OPEN the file
    output = tmp_path / "output.pdf"
    config = CompressConfig(preset=CompressPreset.EBOOK)
    result = compress(protected_pdf, output, config, password="test123")

    assert output.exists()
```

### Coverage Target

- **Core modules** (`src/core/`): >= 85%
- **Utils** (`src/utils/`): >= 90%
- **UI modules** (`src/ui/`): >= 50%

To view detailed coverage:

```bash
python -m pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in your browser
```

---

## Commit Messages

### Format

```
<type>(<scope>): <short description>

<optional body>

<optional footer>
```

### Types

- **fix**: bug fix
- **feat**: new feature
- **refactor**: refactoring without functional change
- **docs**: documentation
- **test**: test addition/modification
- **chore**: build, dependencies, etc.

### Scope (optional)

```
fix(compress): Correct corrupt image resizing
feat(watermark): Add tiled watermark support
test(main_window): Add UI tests for file opening
```

### Examples

```
fix(compress): Handle specific PIL exceptions instead of generic ones
```

```
feat(batch): Support parallel PDF processing

- Add parallel processing with ThreadPoolExecutor
- Limit to 4 concurrent workers to prevent system overload
- Update progress bar in real time
```

```
docs: Add contributing guide CONTRIBUTING.md

Include environment setup, PR workflow, code style, testing.
```

---

## 🔍 Pre-Push Checklist

Before pushing your PR:

- [ ] You ran `git pull origin develop` for latest changes
- [ ] You ran `python -m pytest tests/ -v` — all tests pass
- [ ] You ran `python -m ruff check src/` — zero warnings
- [ ] You ran `python -m ruff format src/` — code formatted
- [ ] You wrote/updated tests for your changes
- [ ] You added docstrings for new functions/classes
- [ ] You updated CHANGELOG.md if necessary
- [ ] Your commit message follows project conventions

---

## ❓ Questions or Issues?

If you have doubts:

1. Open an **issue** with problem details
2. Discuss design in a draft PR if it's a complex feature
3. Look at existing PRs for code style examples

---

## 📄 License

By contributing to PDFusion, you agree that your changes will be licensed under the MIT License, the same as the project.

---

Thank you for contributing to PDFusion! 🎉
