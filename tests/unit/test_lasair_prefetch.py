"""Batched Lasair prefetch writes exactly the cache entries the single-object calls read (no extra API calls)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cosmic_triage.ingest import Cache, LasairClient


def test_prefetch_populates_single_object_keys(tmp_path: Path, monkeypatch: Any) -> None:
    online = LasairClient(Cache(root=tmp_path, offline=False))
    calls: list[dict[str, Any]] = []

    def fake_post(endpoint: str, data: dict[str, Any]) -> Any:
        calls.append(data)
        return [{"_oid": "ZTF25aaaaaaa", "classification": "AGN", "separationArcsec": 0.1},
                {"_oid": "ZTF25bbbbbbb", "classification": "SN", "separationArcsec": 3.2}]

    monkeypatch.setattr(online, "_post", fake_post)
    assert online.prefetch(["ZTF25aaaaaaa", "ZTF25bbbbbbb", "ZTF25ccccccc"], "sherlock_classifications") == 3
    assert len(calls) == 1
    offline = LasairClient(Cache(root=tmp_path, offline=True))
    assert offline.sherlock_object("ZTF25aaaaaaa") == [{"classification": "AGN", "separationArcsec": 0.1}]
    assert offline.sherlock_object("ZTF25ccccccc") == []
    assert online.prefetch(["ZTF25aaaaaaa"], "sherlock_classifications") == 0 and len(calls) == 1
