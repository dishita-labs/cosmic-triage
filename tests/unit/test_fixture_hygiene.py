"""Recorded fixtures must never contain secrets or auth headers (§13.2)."""

from __future__ import annotations

import re

from cosmic_triage import settings
from tests.conftest import FIXTURES

PATTERNS = [
    re.compile(r"Authorization", re.I),
    re.compile(r"\bToken [0-9a-f]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"api_key", re.I),
]


def test_no_secret_values_or_auth_headers_in_fixtures() -> None:
    secrets = settings.secret_values()
    files = [p for p in FIXTURES.rglob("*") if p.is_file()]
    assert files, "no fixtures recorded"
    for p in files:
        text = p.read_text(errors="ignore")
        for s in secrets:
            assert s not in text, f"secret value found in {p}"
        for pat in PATTERNS:
            assert not pat.search(text), f"{pat.pattern} found in {p}"
