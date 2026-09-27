"""Controllo aggiornamenti via GitHub Releases API.

Modulo puro (nessuna dipendenza da PyQt6): la UI lo esegue su un QThread worker
(vedi ui/main_window.py) per non bloccare il main thread con la chiamata di rete.
"""

from __future__ import annotations

import json
import platform
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from utils.config import GITHUB_REPO, PDFUSION_DIR

_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
_TIMEOUT_SECONDS = 6
_MIN_INTERVAL_HOURS = 24

UPDATE_CHECK_STATE_PATH = PDFUSION_DIR / "update_check.json"


class UpdateCheckError(Exception):
    """Controllo aggiornamenti fallito (rete, API, parsing) — non significa
    "nessun aggiornamento disponibile", il chiamante deve distinguere i due casi."""


@dataclass
class ReleaseInfo:
    tag: str
    name: str
    url: str
    body: str
    prerelease: bool
    assets: list[tuple[str, str]] = field(default_factory=list)


def _parse_tag(tag: str) -> tuple[tuple[int, ...], int | None]:
    """"v0.3.0-beta2" -> ((0, 3, 0), 2); "v0.3.0" -> ((0, 3, 0), None)."""
    t = tag.lstrip("vV")
    if "-beta" in t:
        base, _, beta_part = t.partition("-beta")
        beta_n = int(beta_part) if beta_part.isdigit() else 0
    else:
        base, beta_n = t, None
    try:
        parts = tuple(int(p) for p in base.split("."))
    except ValueError:
        parts = (0,)
    return parts, beta_n


def is_newer(current_full_version: str, latest_tag: str) -> bool:
    """True se latest_tag è più recente di current_full_version.

    fetch_latest_release() filtra già le release coerenti col canale corrente
    (beta confrontata solo con pre-release, stable solo con release stabili),
    tranne il caso "promozione a stable della stessa versione base", che qui è
    trattato esplicitamente come aggiornamento disponibile.
    """
    cur_base, cur_beta = _parse_tag(current_full_version)
    lat_base, lat_beta = _parse_tag(latest_tag)
    if lat_base != cur_base:
        return lat_base > cur_base
    if cur_beta is None:
        return False  # stessa versione base, attuale già stable
    if lat_beta is None:
        return True  # promozione beta -> stable della stessa versione base
    return lat_beta > cur_beta


def fetch_latest_release(include_prerelease: bool) -> ReleaseInfo | None:
    """Interroga le release GitHub e ritorna la più recente per il canale richiesto.

    include_prerelease=True cerca tra le pre-release (canale beta),
    include_prerelease=False cerca tra le release stabili (canale stable).
    Ritorna None se non esiste nessuna release di quel canale.
    Solleva UpdateCheckError per problemi di rete/parsing.
    """
    req = urllib.request.Request(
        _API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "PDFusion-update-checker",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError(f"Impossibile contattare GitHub: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UpdateCheckError(f"Risposta GitHub non valida: {exc}") from exc

    if not isinstance(data, list):
        raise UpdateCheckError("Risposta GitHub inattesa")

    for release in data:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        if bool(release.get("prerelease")) != include_prerelease:
            continue
        assets = [
            (a.get("name", ""), a.get("browser_download_url", ""))
            for a in release.get("assets", [])
            if isinstance(a, dict) and a.get("browser_download_url")
        ]
        return ReleaseInfo(
            tag=release.get("tag_name", ""),
            name=release.get("name") or release.get("tag_name", ""),
            url=release.get("html_url", ""),
            body=release.get("body") or "",
            prerelease=bool(release.get("prerelease")),
            assets=assets,
        )
    return None


def pick_asset_url(assets: list[tuple[str, str]]) -> str | None:
    """Sceglie l'asset dell'installer adatto al sistema operativo corrente."""
    system = platform.system()
    for name, url in assets:
        low = name.lower()
        if system == "Windows" and low.endswith(".exe"):
            return url
        if system == "Darwin" and low.endswith(".dmg"):
            return url
        if system == "Linux" and low.endswith(".appimage"):
            return url
    return None


# ---------------------------------------------------------------------------
# Throttle e "ignora questa versione" — persistiti in ~/.pdfusion/update_check.json
# ---------------------------------------------------------------------------


def _load_state() -> dict:
    try:
        if UPDATE_CHECK_STATE_PATH.exists():
            data = json.loads(UPDATE_CHECK_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        UPDATE_CHECK_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        UPDATE_CHECK_STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def should_auto_check() -> bool:
    """True se è passato più di _MIN_INTERVAL_HOURS dall'ultimo controllo automatico."""
    last = _load_state().get("last_check")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    return (datetime.now(UTC) - last_dt) >= timedelta(hours=_MIN_INTERVAL_HOURS)


def mark_checked() -> None:
    state = _load_state()
    state["last_check"] = datetime.now(UTC).isoformat()
    _save_state(state)


def get_skipped_tag() -> str | None:
    return _load_state().get("skipped_tag")


def set_skipped_tag(tag: str) -> None:
    state = _load_state()
    state["skipped_tag"] = tag
    _save_state(state)
