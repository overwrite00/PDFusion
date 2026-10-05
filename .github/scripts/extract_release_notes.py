#!/usr/bin/env python3
"""Estrae da CHANGELOG.md le note della sezione di una release.

Uso::

    python .github/scripts/extract_release_notes.py v0.4.0-beta1 > notes.md

Il tag (``v0.4.0-beta1`` o ``v0.4.0``) corrisponde alla sezione ``## [0.4.0-beta1]`` / ``## [0.4.0]``
del changelog. Esce con codice 1 se la sezione manca o è vuota: una release non deve mai partire con
note generiche o con le note di un'altra versione. ``[Unreleased]`` non viene mai usata.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


class ReleaseNotesError(Exception):
    """Sezione del changelog assente o vuota per la versione richiesta."""


def extract(changelog: str, tag: str) -> str:
    version = tag.removeprefix("v")
    if not version or version.lower() == "unreleased":
        raise ReleaseNotesError(f"Tag non valido per l'estrazione delle note: {tag!r}")

    heading = re.compile(rf"^## \[{re.escape(version)}\]")
    any_heading = re.compile(r"^## \[")
    lines = changelog.replace("\r\n", "\n").split("\n")

    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise ReleaseNotesError(f"CHANGELOG.md non ha la sezione '## [{version}]'.")

    body: list[str] = []
    for line in lines[start + 1 :]:
        if any_heading.match(line):
            break
        body.append(line)

    # Il changelog separa le sezioni con una riga '---': non fa parte delle note.
    while body and body[-1].strip() in ("", "---"):
        body.pop()
    while body and not body[0].strip():
        body.pop(0)

    if not body:
        raise ReleaseNotesError(f"La sezione '## [{version}]' di CHANGELOG.md è vuota.")
    return "\n".join(body) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Uso: {argv[0]} <tag>", file=sys.stderr)
        return 2
    try:
        notes = extract(CHANGELOG.read_text(encoding="utf-8"), argv[1])
        # UTF-8 esplicito: lo stdout di Windows è cp1252 e il changelog contiene "→", "—", ecc.
        sys.stdout.buffer.write(notes.encode("utf-8"))
    except ReleaseNotesError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
