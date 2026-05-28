# Contributing to PDFusion

Thank you for your interest in contributing to PDFusion! This guide will help you set up your development environment and follow the correct workflow.

---

## 📋 Indice

1. [Requisiti](#requisiti)
2. [Setup Ambiente Sviluppo](#setup-ambiente-sviluppo)
3. [Workflow PR](#workflow-pr)
4. [Code Style](#code-style)
5. [Testing](#testing)
6. [Commit Message](#commit-message)

---

## Requisiti

- **Python**: 3.11, 3.12, o 3.13
- **Git**: versione recente
- **Sistema Operativo**: Windows 10+, macOS 11+, o Linux

---

## Setup Ambiente Sviluppo

### 1. Clone il Repository

```bash
git clone https://github.com/overwrite00/PDFusion.git
cd PDFusion
```

### 2. Crea un Virtual Environment

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

### 3. Installa le Dipendenze

```bash
# Dipendenze runtime
pip install -r requirements.txt

# Dipendenze sviluppo (testing, linting, type checking)
pip install -r requirements-dev.txt
```

### 4. Verifica Setup

```bash
python -m pytest tests/ -v --tb=short
```

Se tutti i test passano, l'ambiente è pronto! ✅

---

## Workflow PR

### 1. Crea un Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/nome-feature
```

**Naming convention:**
- `feature/` per nuove funzionalità
- `fix/` per bug fix
- `refactor/` per refactoring
- `docs/` per documentazione

### 2. Fai i Tuoi Cambiamenti

```bash
# Modifica i file
# ...

# Esegui i test localmente
python -m pytest tests/ -v

# Verifica code style
python -m isort src/                # Organizza imports
python -m ruff check src/           # Lint check
python -m ruff format src/          # Auto-format
```

### 3. Commit i Cambiamenti

```bash
git add <file1> <file2> ...
git commit -m "fix: descrizione breve del cambio"
```

**Linee Guida Commit Message:**
- **Tipo**: `fix:`, `feat:`, `refactor:`, `docs:`, `test:`, `chore:`
- **Descrizione**: imperativa, minuscola
- **Lunghezza**: < 72 caratteri per la prima linea
- **Corpo** (opzionale): spiegazione dettagliata dopo una linea vuota

### 4. Push e Crea PR

```bash
git push -u origin feature/nome-feature
```

Poi vai su GitHub e crea una Pull Request. Target base: `develop` (non `main`).

**PR Title Format:**
```
feat: Aggiungi supporto per firma digitale
```

**PR Description Template:**

```markdown
## 📝 Descrizione

Breve descrizione dei cambiamenti.

## ✅ Tipo di Cambio

- [ ] Bug fix (non-breaking change che risolve un issue)
- [ ] Feature (non-breaking change che aggiunge funzionalità)
- [ ] Breaking change (cambio che rompe compatibilità)

## 🧪 Test

Descrivi come hai testato i cambiamenti:

- [ ] Test unitari scritti/aggiornati
- [ ] Manual test completato
- [ ] Coverage >= 80% per i file modificati

## 📋 Checklist

- [ ] Code style (ruff format, ruff check)
- [ ] Type hints (mypy --strict)
- [ ] Docstring per nuove funzioni/classi
- [ ] CHANGELOG.md aggiornato
```

---

## Code Style

### Linting con Ruff

```bash
# Verifica lo style
python -m isort src/ tests/
python -m ruff check src/ tests/

# Auto-fix problemi comuni
python -m ruff check --fix src/ tests/

# Formattazione
python -m ruff format src/ tests/
```

**Configurazione**: Vedi `pyproject.toml` sezione `[tool.ruff]`

### Type Hints

Usa type hints per:
- Parametri di funzione
- Return types di funzione
- Attributi di classe (quando ambigui)

**Esempio:**

```python
def process_pdf(
    input_path: Path,
    options: dict[str, Any] | None = None,
) -> Path:
    """Processa un PDF con le opzioni fornite."""
    ...
```

### Docstring

Usa docstring per:
- Funzioni pubbliche
- Classi
- Moduli complessi

**Formato (Google-style):**

```python
def extract_pages(
    input_path: Path,
    ranges: list[tuple[int, int]],
    output_path: Path,
) -> Path:
    """
    Estrae pagine specifiche da un PDF.

    Args:
        input_path: Percorso del PDF sorgente.
        ranges: Lista di tuple (start, end) 1-based.
        output_path: Percorso del file risultante.

    Returns:
        output_path dopo il salvataggio.

    Raises:
        PDFusionError: Se il file non esiste o è corrotto.
    """
    ...
```

---

## Testing

### Eseguire i Test

```bash
# Tutti i test
python -m pytest tests/ -v

# Test specifico
python -m pytest tests/core/test_compress.py::TestCompress::test_screen_preset -v

# Con coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Scrivere i Test

1. **Test unitari** in `tests/core/test_*.py`
2. **UI tests** in `tests/ui/test_*.py`
3. **Fixtures** in `tests/fixtures/`

**Esempio Test:**

```python
def test_compress_with_screen_preset(tmp_path):
    """Verifica compressione con preset screen."""
    from core.compress import compress, CompressConfig, CompressPreset

    input_pdf = Path(__file__).parent / "fixtures" / "sample.pdf"
    output = tmp_path / "output.pdf"

    config = CompressConfig(preset=CompressPreset.SCREEN)
    result = compress(input_pdf, output, config)

    assert output.exists()
    assert output.stat().st_size < input_pdf.stat().st_size
```

### Coverage Target

- **Core modules** (`src/core/`): >= 85%
- **Utils** (`src/utils/`): >= 90%
- **UI modules** (`src/ui/`): >= 50%

Per visualizzare il coverage dettagliato:

```bash
python -m pytest tests/ --cov=src --cov-report=html
# Apri htmlcov/index.html nel browser
```

---

## Commit Message

### Formato

```
<tipo>(<scope>): <descrizione breve>

<corpo opzionale>

<footer opzionale>
```

### Tipi

- **fix**: bug fix
- **feat**: nuova funzionalità
- **refactor**: refactoring senza cambio funzionale
- **docs**: documentazione
- **test**: aggiunta/modifica test
- **chore**: cambiamenti build, dipendenze, ecc.

### Scope (opzionale)

```
fix(compress): Correggi resize immagini corrotte
feat(watermark): Aggiungi supporto watermark tiled
test(main_window): Aggiungi UI test per file opening
```

### Esempi

```
fix(compress): Gestire eccezioni specifiche PIL non generiche
```

```
feat(batch): Supportare processamento parallelo PDF

- Aggiungi processing parallelo con ThreadPoolExecutor
- Limite di 4 worker simultanei per non sovraccaricare sistema
- Progress bar aggiornata in tempo reale
```

```
docs: Aggiungi guida contributo CONTRIBUTING.md

Includi setup ambiente, workflow PR, code style, testing.
```

---

## 🔍 Checklist Pre-Push

Prima di pushare il tuo PR:

- [ ] Hai fatto `git pull origin develop` per gli ultimi cambiamenti
- [ ] Hai eseguito `python -m pytest tests/ -v` — tutti i test passano
- [ ] Hai eseguito `python -m ruff check src/` — zero warnings
- [ ] Hai eseguito `python -m ruff format src/` — code formattato
- [ ] Hai scritto/aggiornato test per i tuoi cambiamenti
- [ ] Hai aggiunto docstring per funzioni/classi nuove
- [ ] Hai aggiornato CHANGELOG.md se necessario
- [ ] Il commit message segue la convenzione di questo progetto

---

## ❓ Domande o Problemi?

Se hai dubbi:
1. Apri un **issue** con dettagli del problema
2. Discuti il design in una PR draft se è una feature complessa
3. Guarda i PR esistenti per esempi di code style

---

## 📄 Licenza

Contribuendo a PDFusion, accetti che i tuoi cambiamenti siano licenziati sotto MIT License, la stessa del progetto.

---

Grazie di contribuire a PDFusion! 🎉
