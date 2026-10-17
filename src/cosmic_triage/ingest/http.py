"""Shared HTTP client: retries with backoff + jitter, per-host pacing, typed errors, offline guard.

Request headers (which may carry tokens) are never logged or cached.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from cosmic_triage import settings
from cosmic_triage.ingest.errors import ExternalAPIError, NetworkDisabled, RateLimited

log = logging.getLogger(__name__)

USER_AGENT = "cosmic-triage/0.1 (research; contact via repository owner)"


class HttpClient:
    def __init__(
        self,
        name: str,
        timeout_s: float = 120.0,
        max_retries: int = 4,
        min_interval_s: float = 0.0,
        offline: bool | None = None,
        seed: int = 0,
    ) -> None:
        self.name = name
        self.max_retries = max_retries
        self.min_interval_s = min_interval_s
        self.offline = settings.is_offline() if offline is None else offline
        self._client: httpx.Client | None = None
        self._timeout = timeout_s
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self._rng = random.Random(seed)
        self.calls = 0

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            )
        return self._client

    def _pace(self, host: str) -> None:
        if self.min_interval_s <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._last.get(host, 0.0) + self.min_interval_s - now
            self._last[host] = max(now, now + wait)
        if wait > 0:
            time.sleep(wait)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Any = None,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        if self.offline:
            raise NetworkDisabled(f"{self.name}: network disabled (COSMIC_OFFLINE=1): {method} {url}")
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._pace(host)
            try:
                self.calls += 1
                resp = self._http().request(method, url, params=params, data=data, json=json, headers=headers)
            except httpx.TransportError as exc:
                last_exc = exc
                log.warning("%s transport error on attempt %d: %s", self.name, attempt, type(exc).__name__)
            else:
                if resp.status_code == 429:
                    last_exc = RateLimited(self.name, 429, "rate limited")
                elif resp.status_code >= 500:
                    last_exc = ExternalAPIError(self.name, resp.status_code, resp.text[:200])
                elif resp.status_code >= 400:
                    raise ExternalAPIError(self.name, resp.status_code, resp.text[:300])
                else:
                    return resp
            if attempt < self.max_retries:
                backoff = min(60.0, 2.0**attempt) * (0.5 + self._rng.random())
                time.sleep(backoff)
        assert last_exc is not None
        if isinstance(last_exc, ExternalAPIError):
            raise last_exc
        raise ExternalAPIError(self.name, None, f"transport failure: {type(last_exc).__name__}: {last_exc}")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
