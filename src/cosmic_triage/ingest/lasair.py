"""Lasair (ZTF) client (§2.2): SQL queries, objects, Sherlock host context, TNS crossmatch.

Requires ``LASAIR_TOKEN`` (free). The token is sent only as a request header and never cached or logged.
Standard tier is 100 calls/hour, so calls are paced and every response is cached.
"""

from __future__ import annotations

from typing import Any

from cosmic_triage import settings
from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.errors import CredentialMissing, ExternalAPIError
from cosmic_triage.ingest.http import HttpClient

BASE = "https://lasair-ztf.lsst.ac.uk/api"
HOW = (
    "Create a free account at https://lasair-ztf.lsst.ac.uk, copy the API token from your profile, "
    "and add LASAIR_TOKEN=... to .env."
)


class LasairClient:
    name = "lasair"

    def __init__(self, cache: Cache, http: HttpClient | None = None, min_interval_s: float = 36.0) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=min_interval_s, offline=cache.offline)

    def _headers(self) -> dict[str, str]:
        token = settings.get_secret("LASAIR_TOKEN")
        if not token:
            raise CredentialMissing("LASAIR_TOKEN", HOW)
        return {"Authorization": f"Token {token}"}

    def _post(self, endpoint: str, data: dict[str, Any]) -> Any:
        resp = self.http.request("POST", f"{BASE}/{endpoint}/", data=data, headers=self._headers())
        out = resp.json()
        if isinstance(out, dict) and out.get("error"):
            raise ExternalAPIError(self.name, resp.status_code, str(out.get("error"))[:300])
        return out

    def query(self, selected: str, tables: str, conditions: str, limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
        params = {"selected": selected, "tables": tables, "conditions": conditions, "limit": limit, "offset": offset}
        result: list[dict[str, Any]] = self.cache.get_or_fetch(
            self.name, "query", params, lambda: self._post("query", params)
        )
        return result

    def object(self, oid: str, lite: bool = True) -> dict[str, Any]:
        params = {"objectId": oid, "lite": "true" if lite else "false"}
        result: dict[str, Any] = self.cache.get_or_fetch(
            self.name, "object", params, lambda: self._post("object", params)
        )
        return result

    def sherlock(self, ra: float, dec: float) -> dict[str, Any]:
        params = {"ra": round(float(ra), 7), "dec": round(float(dec), 7), "lite": "true"}
        result: dict[str, Any] = self.cache.get_or_fetch(
            self.name, "sherlock_position", params, lambda: self._post("sherlock/position", params)
        )
        return result

    def sherlock_object(self, oid: str) -> list[dict[str, Any]]:
        return self.query(
            "sherlock_classifications.*", "objects,sherlock_classifications", f"objects.objectId='{_safe_oid(oid)}'", 5
        )

    def tns_crossmatch(self, oid: str) -> list[dict[str, Any]]:
        """Lasair's TNS crossmatch rows. NOTE: ``type``/``z`` are *current* TNS values (no classification date)."""
        return self.query("crossmatch_tns.*", "objects,crossmatch_tns", f"objects.objectId='{_safe_oid(oid)}'", 5)


def _safe_oid(oid: str) -> str:
    if not (oid.startswith("ZTF") and oid.isalnum() and len(oid) <= 16):
        raise ValueError(f"not a ZTF object id: {oid!r}")
    return oid
