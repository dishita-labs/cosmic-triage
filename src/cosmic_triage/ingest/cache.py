"""The single disk cache every external call goes through (§13.2).

Key = (client, method, canonical_params). Entries are JSON files holding the request params (never
headers or secrets) and the payload. Bytes payloads are stored base64-encoded. In offline mode a miss
raises ``OfflineCacheMiss``; nothing reaches the network.
"""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cosmic_triage import settings
from cosmic_triage.ingest.errors import IngestError, OfflineCacheMiss


class SecretLeak(IngestError):
    pass


class Cache:
    def __init__(self, root: Path | str | None = None, offline: bool | None = None) -> None:
        self.root = Path(root) if root is not None else settings.cache_dir()
        self.offline = settings.is_offline() if offline is None else offline
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    @staticmethod
    def key(client: str, method: str, params: dict[str, Any]) -> str:
        return settings.sha256_hex(settings.canonical_json({"c": client, "m": method, "p": params}))

    def path(self, client: str, method: str, params: dict[str, Any]) -> Path:
        k = self.key(client, method, params)
        return self.root / client / method / k[:2] / f"{k}.json"

    def has(self, client: str, method: str, params: dict[str, Any]) -> bool:
        return self.path(client, method, params).exists()

    def get(self, client: str, method: str, params: dict[str, Any]) -> Any:
        p = self.path(client, method, params)
        if not p.exists():
            with self._lock:
                self.misses += 1
            raise OfflineCacheMiss(f"cache miss: {client}.{method} {settings.canonical_json(params)[:200]}")
        entry = json.loads(p.read_text())
        with self._lock:
            self.hits += 1
        if entry.get("encoding") == "base64":
            return base64.b64decode(entry["payload"])
        return entry["payload"]

    def put(self, client: str, method: str, params: dict[str, Any], payload: Any) -> None:
        encoding = "json"
        if isinstance(payload, bytes | bytearray):
            payload = base64.b64encode(bytes(payload)).decode()
            encoding = "base64"
        entry = {
            "client": client,
            "method": method,
            "params": params,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "encoding": encoding,
            "payload": payload,
        }
        text = json.dumps(entry, sort_keys=True, allow_nan=True)
        for secret in settings.secret_values():
            if secret in text:
                raise SecretLeak(f"refusing to cache {client}.{method}: payload contains a configured secret")
        p = self.path(client, method, params)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(text)
        tmp.replace(p)

    def get_or_fetch(self, client: str, method: str, params: dict[str, Any], fetch: Callable[[], Any]) -> Any:
        try:
            return self.get(client, method, params)
        except OfflineCacheMiss:
            if self.offline:
                raise
        payload = fetch()
        self.put(client, method, params, payload)
        return payload
