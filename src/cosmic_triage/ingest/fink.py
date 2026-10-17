"""Fink ZTF API client (§2.2): one row per alert with alert-time scores (replay-safe channel)."""

from __future__ import annotations

from typing import Any

from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.http import HttpClient

BASE = "https://api.ztf.fink-portal.org/api/v1"

# Columns needed for the belief channel (M3) and static star/Gaia context for the pre-filter.
SCORE_COLUMNS: tuple[str, ...] = (
    "i:objectId", "i:candid", "i:jd", "i:fid", "i:magpsf", "i:sigmapsf", "i:drb", "i:isdiffpos",
    "i:sgscore1", "i:distpsnr1", "i:srmag1", "i:neargaia", "i:maggaia", "i:ra", "i:dec",
    "d:rf_snia_vs_nonia", "d:snn_snia_vs_nonia", "d:snn_sn_vs_all", "d:cdsxmatch", "d:tns",
)


class FinkClient:
    name = "fink"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=0.1, offline=cache.offline)

    def object_rows(
        self, oid: str, with_upperlim: bool = True, columns: tuple[str, ...] | None = None
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"objectId": oid, "output-format": "json"}
        if with_upperlim:
            body["withupperlim"] = True
        if columns:
            body["columns"] = ",".join(columns)

        def fetch() -> list[dict[str, Any]]:
            data: list[dict[str, Any]] = self.http.request("POST", f"{BASE}/objects", json=body).json()
            return data

        result: list[dict[str, Any]] = self.cache.get_or_fetch(self.name, "objects", body, fetch)
        return result
