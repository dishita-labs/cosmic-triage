"""ALeRCE ZTF API client (§2.2). Forward-pool listing, light curves with non-detections, stamp prior, stamps.

``lc_classifier`` probabilities are *current-state* and must never enter replay; only the stamp
classifier (evaluated on the first alert) is time-honest.
"""

from __future__ import annotations

from typing import Any

from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.errors import ExternalAPIError
from cosmic_triage.ingest.http import HttpClient

BASE = "https://api.alerce.online/ztf/v1"
STAMP_BASE = "https://avro.alerce.online"


class AlerceClient:
    name = "alerce"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=0.05, offline=cache.offline)

    def objects(self, firstmjd: tuple[float, float], page_size: int = 1000, **filters: Any) -> list[dict[str, Any]]:
        """All objects whose ALeRCE ``firstmjd`` (first alert) lies in [a, b). Paginates fully."""
        params: dict[str, Any] = {"firstmjd": [float(firstmjd[0]), float(firstmjd[1])], "page_size": page_size}
        params.update({k: v for k, v in sorted(filters.items())})

        def fetch() -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            page = 1
            while True:
                q: list[tuple[str, Any]] = [("firstmjd", firstmjd[0]), ("firstmjd", firstmjd[1])]
                for k, v in filters.items():
                    if isinstance(v, list | tuple):
                        q.extend((k, x) for x in v)
                    else:
                        q.append((k, v))
                q += [("page_size", page_size), ("page", page), ("order_by", "oid"), ("order_mode", "ASC")]
                data = self.http.request("GET", f"{BASE}/objects/", params=q).json()
                batch = data.get("items", [])
                items.extend(batch)
                # ALeRCE reports has_next=false when `total` is not computed; a full page means "maybe more".
                if len(batch) < page_size and not data.get("has_next"):
                    return items
                page += 1

        result: list[dict[str, Any]] = self.cache.get_or_fetch(self.name, "objects", params, fetch)
        return result

    def lightcurve(self, oid: str) -> dict[str, Any]:
        def fetch() -> dict[str, Any]:
            data: dict[str, Any] = self.http.request("GET", f"{BASE}/objects/{oid}/lightcurve").json()
            if "detections" not in data:
                raise ExternalAPIError(self.name, None, f"unexpected lightcurve shape for {oid}")
            return data

        result: dict[str, Any] = self.cache.get_or_fetch(self.name, "lightcurve", {"oid": oid}, fetch)
        return result

    def probabilities(self, oid: str) -> list[dict[str, Any]]:
        def fetch() -> list[dict[str, Any]]:
            data: list[dict[str, Any]] = self.http.request("GET", f"{BASE}/objects/{oid}/probabilities").json()
            return data

        result: list[dict[str, Any]] = self.cache.get_or_fetch(self.name, "probabilities", {"oid": oid}, fetch)
        return result

    def stamp(self, oid: str, candid: str, kind: str = "science", fmt: str = "png") -> bytes:
        """Cutout bytes. ``fmt="fits"`` returns gzipped FITS (raw pixel values, as BTSbot expects)."""
        if kind not in ("science", "template", "difference") or fmt not in ("png", "fits"):
            raise ValueError((kind, fmt))

        def fetch() -> bytes:
            resp = self.http.request(
                "GET", f"{STAMP_BASE}/get_stamp",
                params={"oid": oid, "candid": candid, "type": kind, "format": fmt},
            )
            return resp.content

        key: dict[str, str] = {"oid": oid, "candid": str(candid), "kind": kind}
        if fmt != "png":
            key["fmt"] = fmt
        result: bytes = self.cache.get_or_fetch(self.name, "stamp", key, fetch)
        return result
