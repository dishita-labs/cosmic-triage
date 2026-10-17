"""ZTF Bright Transient Survey catalog — ground truth. **Only `replay` may import this module** (§13.2).

The Sample Explorer CSV is pulled without quality/purity filters so it contains the full saved list
including unclassified candidates (§2.2). It lacks a classification date, so the catalog is snapshotted
by download date.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

import pandas as pd

from cosmic_triage.contracts import Label
from cosmic_triage.contracts.units import bts_peakt_to_mjd
from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.errors import OfflineCacheMiss
from cosmic_triage.ingest.http import HttpClient

URL = "https://sites.astro.caltech.edu/ztf/bts/explorer.php"
# No `quality`/`purity` flags and an empty peak-mag bound -> the full saved list incl. unclassified.
UNFILTERED_PARAMS: dict[str, str] = {
    "f": "s", "format": "csv", "endpeakmag": "", "showsavedate": "y", "showdiscdate": "y", "showlastdate": "y",
}


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


class BTSCatalog:
    name = "bts"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, offline=cache.offline)
        self._df: pd.DataFrame | None = None
        self._by_oid: dict[str, dict[str, Any]] = {}

    def fetch_csv(self, snapshot_date: str) -> str:
        params = {"snapshot_date": snapshot_date, **UNFILTERED_PARAMS}
        try:
            text: str = self.cache.get(self.name, "explorer_csv", params)
            return text
        except OfflineCacheMiss:
            if self.cache.offline or snapshot_date != date.today().isoformat():
                raise OfflineCacheMiss(
                    f"BTS snapshot {snapshot_date} not cached (only today's can be downloaded)"
                ) from None
        text = self.http.request("GET", URL, params=UNFILTERED_PARAMS).text
        self.cache.put(self.name, "explorer_csv", params, text)
        return text

    def load(self, snapshot_date: str) -> pd.DataFrame:
        raw = self.fetch_csv(snapshot_date).lstrip()
        df = pd.read_csv(io.StringIO(raw), dtype=str, keep_default_na=False)
        df["peak_mjd"] = [bts_peakt_to_mjd(v) if (v := _num(x)) is not None else None for x in df["peakt"]]
        df["peakmag_f"] = [_num(x) for x in df["peakmag"]]
        df["redshift_f"] = [_num(x) for x in df["redshift"]]
        df["classified"] = df["type"].str.strip().ne("-") & df["type"].str.strip().ne("")
        df["savedate_mjd"] = [
            (pd.Timestamp(s).to_julian_date() - 2400000.5) if s and s != "-" else None for s in df["savedate"]
        ] if "savedate" in df.columns else None
        self._df = df
        self._by_oid = {str(r["ZTFID"]): {str(k): v for k, v in r.items()} for r in df.to_dict("records")}
        return df

    def _require(self) -> dict[str, dict[str, Any]]:
        if self._df is None:
            raise RuntimeError("call load(snapshot_date) first")
        return self._by_oid

    def row(self, oid: str) -> dict[str, Any] | None:
        return self._require().get(oid)

    def label(self, oid: str, scored_regime: bool) -> Label:
        """§6.4: saved+classified -> class; saved+unclassified -> unknown;
        never-saved & filter-passing & bright -> contaminant. Unsaved objects outside the scored regime have no label."""
        r = self._require().get(oid)
        if r is not None:
            return "class" if r["classified"] else "unknown"
        if scored_regime:
            return "contaminant"
        raise ValueError(f"{oid} is not in BTS and not in the scored regime: no label")
