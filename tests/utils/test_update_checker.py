"""Test per utils.update_checker (controllo aggiornamenti via GitHub Releases).

Regole di questa suite:
- nessuna rete: ``urllib.request.urlopen`` è sempre sostituita da un finto;
- nessuna scrittura in ``~/.pdfusion``: ``UPDATE_CHECK_STATE_PATH`` è una costante di
  modulo letta a *call time* da ``_load_state``/``_save_state``, quindi ogni test che
  tocca lo stato la reindirizza su ``tmp_path`` (fixture ``state_file``) e un controllo
  finale verifica che il file reale dell'utente non sia stato toccato.
"""

from __future__ import annotations

import json
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from utils import update_checker as uc
from utils.update_checker import (
    ReleaseInfo,
    UpdateCheckError,
    _parse_tag,
    fetch_latest_release,
    get_skipped_tag,
    is_newer,
    mark_checked,
    pick_asset_url,
    set_skipped_tag,
    should_auto_check,
)

_REAL_STATE_PATH = uc.UPDATE_CHECK_STATE_PATH


def _real_state_fingerprint() -> tuple[bool, int | None]:
    try:
        return True, _REAL_STATE_PATH.stat().st_mtime_ns
    except OSError:
        return False, None


@pytest.fixture(autouse=True)
def _never_touch_real_state():
    """Fallisce se un test di questo modulo scrive nel vero ~/.pdfusion/update_check.json."""
    before = _real_state_fingerprint()
    yield
    assert _real_state_fingerprint() == before, "il test ha toccato il file di stato reale"


@pytest.fixture
def state_file(monkeypatch, tmp_path) -> Path:
    path = tmp_path / "pdfusion" / "update_check.json"
    monkeypatch.setattr(uc, "UPDATE_CHECK_STATE_PATH", path)
    return path


# ---------------------------------------------------------------------------
# Parsing e confronto versioni
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.3.0", ((0, 3, 0), None)),
        ("0.3.0", ((0, 3, 0), None)),
        ("V1.2.3", ((1, 2, 3), None)),
        ("v0.3.1-beta2", ((0, 3, 1), 2)),
        ("0.3.1-beta10", ((0, 3, 1), 10)),
        ("v1.2.3-beta", ((1, 2, 3), 0)),  # beta senza numero
        ("vfoo", ((0,), None)),  # tag non numerico: non solleva
        ("", ((0,), None)),
    ],
)
def test_parse_tag(tag, expected):
    assert _parse_tag(tag) == expected


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        # stable -> stable
        ("0.3.0", "v0.3.1", True),
        ("0.3.0", "v0.3.0", False),
        ("0.3.1", "v0.3.0", False),
        # il confronto è numerico, non lessicografico
        ("0.9.0", "v0.10.0", True),
        ("0.10.0", "v0.9.0", False),
        # beta -> beta
        ("0.3.1-beta1", "v0.3.1-beta2", True),
        ("0.3.1-beta2", "v0.3.1-beta2", False),
        ("0.3.1-beta3", "v0.3.1-beta2", False),
        ("0.3.1-beta2", "v0.3.1-beta10", True),
        # promozione beta -> stable della stessa versione base
        ("0.3.0-beta3", "v0.3.0", True),
        # stable -> beta della stessa base: non è un aggiornamento
        ("0.3.0", "v0.3.0-beta3", False),
        # base più alta vince sempre, beta o no
        ("0.3.0", "v0.3.1-beta1", True),
        ("0.3.1-beta1", "v0.3.0", False),
    ],
)
def test_is_newer(current, latest, expected):
    assert is_newer(current, latest) is expected


# ---------------------------------------------------------------------------
# Scelta dell'installer per OS
# ---------------------------------------------------------------------------

_ASSETS = [
    ("PDFusion-0.3.0-linux.AppImage", "https://x/linux"),
    ("PDFusion-0.3.0-macos.dmg", "https://x/mac"),
    ("PDFusion-0.3.0-windows-setup.exe", "https://x/win"),
]


@pytest.mark.parametrize(
    ("system", "expected"),
    [("Windows", "https://x/win"), ("Darwin", "https://x/mac"), ("Linux", "https://x/linux")],
)
def test_pick_asset_url_per_platform(monkeypatch, system, expected):
    monkeypatch.setattr(uc.platform, "system", lambda: system)
    assert pick_asset_url(_ASSETS) == expected


def test_pick_asset_url_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(uc.platform, "system", lambda: "Linux")
    assert pick_asset_url([("PDFusion.APPIMAGE", "https://x/l")]) == "https://x/l"


def test_pick_asset_url_none_when_no_match(monkeypatch):
    monkeypatch.setattr(uc.platform, "system", lambda: "Windows")
    assert pick_asset_url([("notes.txt", "https://x/n")]) is None
    assert pick_asset_url([]) is None
    monkeypatch.setattr(uc.platform, "system", lambda: "FreeBSD")
    assert pick_asset_url(_ASSETS) is None


# ---------------------------------------------------------------------------
# Stato persistito: throttle 24h e "ignora questa versione"
# ---------------------------------------------------------------------------


def test_should_auto_check_true_without_state(state_file):
    assert not state_file.exists()
    assert should_auto_check() is True


def test_mark_checked_creates_state_and_throttles(state_file):
    mark_checked()
    assert state_file.exists()
    assert "last_check" in json.loads(state_file.read_text(encoding="utf-8"))
    assert should_auto_check() is False


@pytest.mark.parametrize(("hours_ago", "expected"), [(1, False), (23, False), (25, True)])
def test_should_auto_check_respects_24h_interval(state_file, hours_ago, expected):
    state_file.parent.mkdir(parents=True)
    last = (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()
    state_file.write_text(json.dumps({"last_check": last}), encoding="utf-8")
    assert should_auto_check() is expected


def test_should_auto_check_true_when_last_check_is_garbage(state_file):
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"last_check": "not-a-date"}), encoding="utf-8")
    assert should_auto_check() is True


@pytest.mark.parametrize("content", ["{ not json", "[]", '"a string"', ""])
def test_corrupt_or_non_dict_state_is_treated_as_empty(state_file, content):
    state_file.parent.mkdir(parents=True)
    state_file.write_text(content, encoding="utf-8")
    assert should_auto_check() is True
    assert get_skipped_tag() is None


def test_skipped_tag_roundtrip_and_independent_from_last_check(state_file):
    assert get_skipped_tag() is None
    mark_checked()
    set_skipped_tag("v0.3.1")
    assert get_skipped_tag() == "v0.3.1"
    assert should_auto_check() is False  # set_skipped_tag non deve perdere last_check
    set_skipped_tag("v0.3.2")
    assert get_skipped_tag() == "v0.3.2"


def test_save_state_failure_is_swallowed(monkeypatch, tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")  # il "genitore" è un file: mkdir fallisce
    monkeypatch.setattr(uc, "UPDATE_CHECK_STATE_PATH", blocker / "update_check.json")
    mark_checked()  # non deve sollevare
    assert get_skipped_tag() is None


# ---------------------------------------------------------------------------
# fetch_latest_release (rete finta)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._raw


def _install_fake_urlopen(monkeypatch, payload=None, exc=None):
    calls: list[tuple[object, float | None]] = []

    def fake_urlopen(req, timeout=None):
        calls.append((req, timeout))
        if exc is not None:
            raise exc
        return _FakeResponse(payload)

    monkeypatch.setattr(uc.urllib.request, "urlopen", fake_urlopen)
    return calls


def _rel(tag, *, prerelease=False, draft=False, **extra):
    return {
        "tag_name": tag,
        "name": f"PDFusion {tag}",
        "html_url": f"https://github.com/o/r/releases/tag/{tag}",
        "body": f"notes for {tag}",
        "prerelease": prerelease,
        "draft": draft,
        "assets": [{"name": f"{tag}.exe", "browser_download_url": f"https://x/{tag}.exe"}],
        **extra,
    }


def test_fetch_stable_channel_returns_first_stable(monkeypatch):
    _install_fake_urlopen(
        monkeypatch,
        [_rel("v0.3.1-beta1", prerelease=True), _rel("v0.3.0"), _rel("v0.2.10")],
    )
    rel = fetch_latest_release(include_prerelease=False)
    assert isinstance(rel, ReleaseInfo)
    assert rel.tag == "v0.3.0"
    assert rel.prerelease is False
    assert rel.body == "notes for v0.3.0"
    assert rel.assets == [("v0.3.0.exe", "https://x/v0.3.0.exe")]


def test_fetch_beta_channel_skips_drafts(monkeypatch):
    _install_fake_urlopen(
        monkeypatch,
        [
            _rel("v0.3.2-beta1", prerelease=True, draft=True),
            _rel("v0.3.1-beta2", prerelease=True),
            _rel("v0.3.0"),
        ],
    )
    rel = fetch_latest_release(include_prerelease=True)
    assert rel is not None and rel.tag == "v0.3.1-beta2" and rel.prerelease is True


# --- canale beta: vede anche le release stabili (promozione beta -> stable) -------------
# Prima del fix fetch_latest_release(include_prerelease=True) scartava le stabili, quindi
# la "promozione a stable della stessa versione base" gestita da is_newer() non poteva mai
# scattare: un utente su 0.3.0-beta3 non vedeva mai la v0.3.0.


def test_fetch_beta_channel_offers_stable_promotion(monkeypatch):
    _install_fake_urlopen(
        monkeypatch, [_rel("v0.3.0"), _rel("v0.3.0-beta3", prerelease=True)]
    )
    rel = fetch_latest_release(include_prerelease=True)
    assert rel is not None and rel.tag == "v0.3.0" and rel.prerelease is False
    assert is_newer("0.3.0-beta3", rel.tag) is True


def test_fetch_beta_channel_prefers_newer_beta_over_older_stable(monkeypatch):
    _install_fake_urlopen(
        monkeypatch, [_rel("v0.3.1-beta1", prerelease=True), _rel("v0.3.0")]
    )
    rel = fetch_latest_release(include_prerelease=True)
    assert rel is not None and rel.tag == "v0.3.1-beta1"


def test_fetch_picks_highest_version_regardless_of_api_order(monkeypatch):
    # stessa base: la stabile batte la beta anche se l'API la elenca dopo
    _install_fake_urlopen(
        monkeypatch, [_rel("v0.3.0-beta3", prerelease=True), _rel("v0.3.0")]
    )
    assert fetch_latest_release(include_prerelease=True).tag == "v0.3.0"
    # un hotfix di una linea più vecchia pubblicato dopo non nasconde la beta più nuova
    _install_fake_urlopen(
        monkeypatch, [_rel("v0.2.11"), _rel("v0.3.0-beta3", prerelease=True)]
    )
    assert fetch_latest_release(include_prerelease=True).tag == "v0.3.0-beta3"


def test_fetch_stable_channel_never_returns_a_prerelease(monkeypatch):
    _install_fake_urlopen(
        monkeypatch, [_rel("v0.4.0-beta1", prerelease=True), _rel("v0.3.0")]
    )
    rel = fetch_latest_release(include_prerelease=False)
    assert rel is not None and rel.tag == "v0.3.0" and rel.prerelease is False


def test_fetch_returns_none_when_channel_has_no_release(monkeypatch):
    _install_fake_urlopen(monkeypatch, [_rel("v0.3.1-beta1", prerelease=True)])
    assert fetch_latest_release(include_prerelease=False) is None
    _install_fake_urlopen(monkeypatch, [])
    assert fetch_latest_release(include_prerelease=True) is None


def test_fetch_tolerates_missing_fields_and_bad_entries(monkeypatch):
    raw = {
        "tag_name": "v1.0.0",
        "name": None,
        "html_url": "u",
        "body": None,
        "prerelease": False,
        "assets": [
            {"name": "ok.exe", "browser_download_url": "https://x/ok"},
            {"name": "no-url.exe"},  # senza URL: scartato
            "not-a-dict",  # scartato
        ],
    }
    _install_fake_urlopen(monkeypatch, ["junk", raw])
    rel = fetch_latest_release(include_prerelease=False)
    assert rel is not None
    assert rel.name == "v1.0.0"  # ripiega sul tag
    assert rel.body == ""
    assert rel.assets == [("ok.exe", "https://x/ok")]


def test_fetch_request_targets_github_api_only_with_fixed_headers(monkeypatch):
    calls = _install_fake_urlopen(monkeypatch, [])
    fetch_latest_release(include_prerelease=False)
    assert len(calls) == 1
    req, timeout = calls[0]
    assert req.full_url == f"https://api.github.com/repos/{uc.GITHUB_REPO}/releases"
    assert req.get_method() == "GET" and req.data is None  # nessun corpo: nessun dato inviato
    assert {k.lower(): v for k, v in req.header_items()} == {
        "accept": "application/vnd.github+json",
        "user-agent": "PDFusion-update-checker",
    }
    assert timeout == 6


@pytest.mark.parametrize(
    "exc",
    [urllib.error.URLError("offline"), TimeoutError("slow"), ConnectionResetError("reset")],
)
def test_fetch_network_errors_become_update_check_error(monkeypatch, exc):
    _install_fake_urlopen(monkeypatch, exc=exc)
    with pytest.raises(UpdateCheckError):
        fetch_latest_release(include_prerelease=False)


def test_fetch_invalid_json_becomes_update_check_error(monkeypatch):
    _install_fake_urlopen(monkeypatch, b"<html>not json</html>")
    with pytest.raises(UpdateCheckError):
        fetch_latest_release(include_prerelease=False)


def test_fetch_non_list_payload_becomes_update_check_error(monkeypatch):
    _install_fake_urlopen(monkeypatch, {"message": "API rate limit exceeded"})
    with pytest.raises(UpdateCheckError):
        fetch_latest_release(include_prerelease=False)
