from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from cosmic_triage.ingest import Cache, ExternalAPIError, HttpClient, NetworkDisabled, OfflineCacheMiss
from cosmic_triage.ingest.cache import SecretLeak


def test_put_get_roundtrip(tmp_path: Path) -> None:
    c = Cache(root=tmp_path, offline=False)
    c.put("x", "m", {"a": 1, "b": [1, 2]}, {"payload": [1, 2, 3]})
    assert c.get("x", "m", {"b": [1, 2], "a": 1}) == {"payload": [1, 2, 3]}  # key is order-independent


def test_bytes_payload(tmp_path: Path) -> None:
    c = Cache(root=tmp_path, offline=False)
    c.put("x", "stamp", {"id": 1}, b"\x89PNG\r\n")
    assert c.get("x", "stamp", {"id": 1}) == b"\x89PNG\r\n"


def test_offline_miss_raises_and_never_fetches(tmp_path: Path) -> None:
    c = Cache(root=tmp_path, offline=True)
    called = []
    with pytest.raises(OfflineCacheMiss):
        c.get_or_fetch("x", "m", {"q": 1}, lambda: called.append(1))
    assert not called


def test_online_miss_fetches_once(tmp_path: Path) -> None:
    c = Cache(root=tmp_path, offline=False)
    calls = []

    def fetch() -> dict[str, int]:
        calls.append(1)
        return {"v": 1}

    assert c.get_or_fetch("x", "m", {}, fetch) == {"v": 1}
    assert c.get_or_fetch("x", "m", {}, fetch) == {"v": 1}
    assert len(calls) == 1


def test_cache_refuses_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-SECRET-123456")
    c = Cache(root=tmp_path, offline=False)
    with pytest.raises(SecretLeak):
        c.put("x", "m", {}, {"echo": "header was sk-test-SECRET-123456"})


def test_http_offline_guard() -> None:
    with pytest.raises(NetworkDisabled):
        HttpClient("t", offline=True).request("GET", "https://example.org")


def test_http_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    seq = iter([503, 429, 200])
    transport = httpx.MockTransport(lambda req: httpx.Response(next(seq), json={"ok": True}))
    h = HttpClient("t", offline=False, max_retries=3)
    h._client = httpx.Client(transport=transport)
    monkeypatch.setattr("cosmic_triage.ingest.http.time.sleep", lambda s: None)
    assert h.request("GET", "https://example.org/x").json() == {"ok": True}
    assert h.calls == 3


def test_http_4xx_is_typed_error() -> None:
    h = HttpClient("t", offline=False, max_retries=3)
    h._client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404, text="nope")))
    with pytest.raises(ExternalAPIError) as ei:
        h.request("GET", "https://example.org/x")
    assert ei.value.status == 404
    assert h.calls == 1
