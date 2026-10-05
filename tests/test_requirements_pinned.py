"""Ogni dipendenza runtime, anche transitiva, deve essere fissata in ``requirements.txt``.

Senza il blocco delle transitive (MarkupSafe, lxml, PyQt6-Qt6...) due build dello stesso commit
possono contenere versioni diverse di una libreria, e un aggiornamento upstream entra nel binario
senza passare da una PR. Il test legge ``requirements.txt``, ricostruisce la chiusura delle
dipendenze con i metadati dei pacchetti installati e verifica che ogni pacchetto sia presente con
``==`` e che la versione fissata sia quella installata.
"""

import re
from importlib import metadata
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def _pinned() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.\-]+)==([^\s;]+)", line)
        assert m, f"riga non fissata con ==: {line!r}"
        pins[canonicalize_name(m.group(1))] = m.group(2)
    return pins


def _closure(roots: set[str]) -> set[str]:
    seen: set[str] = set()
    todo = list(roots)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for raw in metadata.requires(name) or []:
            req = Requirement(raw)
            if req.marker is not None and not req.marker.evaluate({"extra": ""}):
                continue
            todo.append(canonicalize_name(req.name))
    return seen


def test_every_line_is_pinned_exactly():
    assert _pinned()  # _pinned() asserisce già che ogni riga usi ==


def test_runtime_dependency_closure_is_fully_pinned():
    pins = _pinned()
    missing = sorted(_closure(set(pins)) - set(pins))
    assert not missing, f"dipendenze transitive non fissate in requirements.txt: {missing}"


@pytest.mark.parametrize("name", sorted(_pinned()))
def test_pinned_version_matches_installed(name):
    pins = _pinned()
    assert metadata.version(name) == pins[name]
