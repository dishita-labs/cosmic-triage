"""Static-catalog cone searches (SIMBAD, NED) via TAP, through the shared cache (§2.2; M2 Investigator tools)."""

from __future__ import annotations

import csv
import io
from typing import Any

from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.http import HttpClient

SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
NED_TAP = "https://ned.ipac.caltech.edu/tap/sync"


def _tap_csv(http: HttpClient, url: str, adql: str) -> list[dict[str, Any]]:
    resp = http.request(
        "POST", url, data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "RESPONSEFORMAT": "csv", "QUERY": adql}
    )
    return list(csv.DictReader(io.StringIO(resp.text)))


class SimbadClient:
    name = "simbad"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=0.25, offline=cache.offline)

    def cone(self, ra: float, dec: float, radius_arcsec: float = 10.0, top: int = 25) -> list[dict[str, Any]]:
        params = {"ra": round(ra, 6), "dec": round(dec, 6), "r": radius_arcsec, "top": top}
        adql = (
            f"SELECT TOP {top} main_id, ra, dec, otype, rvz_redshift, "
            f"DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', {ra}, {dec})) * 3600 AS sep_arcsec "
            f"FROM basic WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra}, {dec}, {radius_arcsec / 3600.0}))=1 "
            "ORDER BY sep_arcsec"
        )
        result: list[dict[str, Any]] = self.cache.get_or_fetch(
            self.name, "cone", params, lambda: _tap_csv(self.http, SIMBAD_TAP, adql)
        )
        return result


class NedClient:
    name = "ned"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=1.0, offline=cache.offline)

    def cone(self, ra: float, dec: float, radius_arcsec: float = 10.0, top: int = 25) -> list[dict[str, Any]]:
        params = {"ra": round(ra, 6), "dec": round(dec, 6), "r": radius_arcsec, "top": top}
        adql = (
            f"SELECT TOP {top} prefname, ra, dec, prefphytype, z, zflag FROM NEDTAP.objdir "
            f"WHERE CONTAINS(POINT('J2000', ra, dec), CIRCLE('J2000', {ra}, {dec}, {radius_arcsec / 3600.0}))=1"
        )
        result: list[dict[str, Any]] = self.cache.get_or_fetch(
            self.name, "cone", params, lambda: _tap_csv(self.http, NED_TAP, adql)
        )
        return result
