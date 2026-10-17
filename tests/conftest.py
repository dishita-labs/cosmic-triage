"""Test harness: no network, ever (§13.2). Fixtures are read from tests/fixtures/ in offline mode."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
os.environ["COSMIC_OFFLINE"] = "1"
os.environ["COSMIC_CACHE_DIR"] = str(FIXTURES / "cache")


class NetworkAccessInTest(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def guard(*args: object, **kwargs: object) -> None:
        raise NetworkAccessInTest(f"test attempted network access: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.setattr(socket, "getaddrinfo", guard)
    monkeypatch.setenv("COSMIC_OFFLINE", "1")


@pytest.fixture
def fixture_cache():  # type: ignore[no-untyped-def]
    from cosmic_triage.ingest import Cache

    return Cache(root=FIXTURES / "cache", offline=True)
