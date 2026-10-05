"""``.github/scripts/extract_release_notes.py``: le note di una release vengono dalla SUA sezione.

I workflow ``build-develop.yml`` (beta) e ``build-release.yml`` (stabile) usano lo script per il corpo
della release GitHub. Se la sezione manca o è vuota, lo script deve fallire (e con lui la build, prima
dei job lunghi), mai ripiegare su note generiche o su quelle di un'altra versione.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "extract_release_notes.py"

_spec = importlib.util.spec_from_file_location("extract_release_notes", SCRIPT)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

CHANGELOG = """\
# Changelog

---

## [Unreleased]

### Added
- unreleased thing

---

## [0.4.0] — 2026-11-01

### Added
- stable feature
- beta1 feature (accumulated)

---

## [0.4.0-beta2] — 2026-10-20

### Fixed
- beta2 fix

---

## [0.4.0-beta1] — 2026-10-05

### Added
- beta1 feature → with unicode — dash

---

## [0.3.0] — 2026-09-27

- old
"""


def test_beta_tag_reads_its_own_section():
    notes = mod.extract(CHANGELOG, "v0.4.0-beta1")
    assert notes == "### Added\n- beta1 feature → with unicode — dash\n"


def test_second_beta_does_not_repeat_the_first():
    notes = mod.extract(CHANGELOG, "v0.4.0-beta2")
    assert "beta2 fix" in notes
    assert "beta1" not in notes


def test_stable_tag_reads_the_stable_section_not_a_beta():
    notes = mod.extract(CHANGELOG, "v0.4.0")
    assert "stable feature" in notes
    assert "beta2 fix" not in notes


def test_unreleased_is_never_used():
    notes = mod.extract(CHANGELOG, "v0.4.0")
    assert "unreleased thing" not in notes


def test_section_separator_and_heading_are_not_part_of_the_notes():
    notes = mod.extract(CHANGELOG, "v0.4.0")
    assert "---" not in notes
    assert "## [" not in notes
    assert not notes.endswith("\n\n")


def test_missing_section_is_an_error():
    with pytest.raises(mod.ReleaseNotesError, match="0.9.9"):
        mod.extract(CHANGELOG, "v0.9.9")


def test_version_prefix_does_not_match_a_longer_version():
    # "0.4.0-beta" non deve pescare "0.4.0-beta1"; "0.4" non deve pescare "0.4.0"
    for tag in ("v0.4.0-beta", "v0.4", "v0.4.0-beta11"):
        with pytest.raises(mod.ReleaseNotesError):
            mod.extract(CHANGELOG, tag)


def test_dots_are_literal_not_regex_wildcards():
    # "0.4.0" non deve corrispondere a un'intestazione "0a4b0" (il '.' non è un jolly)
    with pytest.raises(mod.ReleaseNotesError):
        mod.extract("## [0a4b0] — 2026-01-01\n- x\n", "v0.4.0")


def test_empty_section_is_an_error():
    text = "## [Unreleased]\n\n## [1.0.0] — 2026-01-01\n\n---\n\n## [0.9.0] — 2025-01-01\n- x\n"
    with pytest.raises(mod.ReleaseNotesError, match="vuota"):
        mod.extract(text, "v1.0.0")


def test_last_section_of_the_file_is_read_to_the_end():
    assert mod.extract(CHANGELOG, "v0.3.0") == "- old\n"


@pytest.mark.parametrize("tag", ["", "v", "vUnreleased", "Unreleased"])
def test_unusable_tags_are_rejected(tag):
    with pytest.raises(mod.ReleaseNotesError):
        mod.extract(CHANGELOG, tag)


def test_crlf_changelog_is_handled():
    notes = mod.extract(CHANGELOG.replace("\n", "\r\n"), "v0.4.0-beta1")
    assert notes == "### Added\n- beta1 feature → with unicode — dash\n"


def test_real_changelog_has_notes_for_the_last_stable_release():
    notes = mod.extract((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), "v0.3.0")
    assert notes.strip()
    assert "## [" not in notes


def _run(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, cwd=ROOT)


def test_cli_writes_utf8_to_stdout_even_with_unicode_changelog():
    result = _run("v0.3.0")
    assert result.returncode == 0, result.stderr
    assert "→".encode() in result.stdout  # il changelog 0.3.0 contiene frecce


def test_cli_fails_with_exit_code_1_for_a_missing_section():
    result = _run("v9.9.9")
    assert result.returncode == 1
    assert result.stdout == b""
    assert b"9.9.9" in result.stderr


def test_cli_without_arguments_is_a_usage_error():
    assert _run().returncode == 2
