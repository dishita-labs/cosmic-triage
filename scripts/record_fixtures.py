"""Record HTTP fixtures for offline tests (§13.2): copy selected cache entries into tests/fixtures/cache.

Entries hold request params and payloads only — never headers or tokens; Cache.put refuses any payload that
contains a configured secret, and tests/unit/test_fixture_hygiene.py re-checks every fixture file.
Run online once: uv run python scripts/record_fixtures.py
"""

from __future__ import annotations

import io
import sys

import pandas as pd

from cosmic_triage.ingest import AlerceClient, Cache, FinkClient, LasairClient
from cosmic_triage.ingest.bts import UNFILTERED_PARAMS
from cosmic_triage.ingest.catalogs import NedClient, SimbadClient
from cosmic_triage.ingest.corpora import AstroNoteClient, AtelClient, GcnClient
from cosmic_triage.settings import PROJECT_ROOT, load_config

PROBE = "ZTF25aaafbbk"
RA, DEC = 197.33599, 46.23975
BTS_FIXTURE_OIDS_EXTRA = 400  # rows kept in the trimmed BTS fixture


def main() -> int:
    live = Cache()
    fx = Cache(root=PROJECT_ROOT / "tests" / "fixtures" / "cache", offline=False)

    def copy(client: str, method: str, params: dict, payload: object | None = None) -> None:
        if payload is None:
            payload = live.get(client, method, params)
        fx.put(client, method, params, payload)
        print(f"recorded {client}.{method} {str(params)[:90]}")

    al, fk, la = AlerceClient(live), FinkClient(live), LasairClient(live)
    al.lightcurve(PROBE)
    copy("alerce", "lightcurve", {"oid": PROBE})
    al.probabilities(PROBE)
    copy("alerce", "probabilities", {"oid": PROBE})
    cand = str(next(d["candid"] for d in al.lightcurve(PROBE)["detections"] if d.get("has_stamp")))
    al.stamp(PROBE, cand, "science")
    copy("alerce", "stamp", {"oid": PROBE, "candid": cand, "kind": "science"})
    small = al.objects((60760.2, 60760.25), page_size=1000, ndet=[2, 100000])
    copy("alerce", "objects", {"firstmjd": [60760.2, 60760.25], "page_size": 1000, "ndet": [2, 100000]}, small)
    body = {"objectId": PROBE, "output-format": "json", "withupperlim": True}
    fk.object_rows(PROBE)
    copy("fink", "objects", body)
    for rows, sel in ((la.tns_crossmatch(PROBE), "crossmatch_tns.*"), (la.sherlock_object(PROBE), "sherlock_classifications.*")):
        tables = "objects,crossmatch_tns" if "tns" in sel else "objects,sherlock_classifications"
        copy("lasair", "query", {"selected": sel, "tables": tables, "conditions": f"objects.objectId='{PROBE}'",
                                 "limit": 5, "offset": 0}, rows)
    SimbadClient(live).cone(186.27, 12.887, 60)
    copy("simbad", "cone", {"ra": 186.27, "dec": 12.887, "r": 60, "top": 25})
    NedClient(live).cone(186.27, 12.887, 60)
    copy("ned", "cone", {"ra": 186.27, "dec": 12.887, "r": 60, "top": 25})
    GcnClient(live).circular(39000)
    copy("gcn", "circular", {"id": 39000})
    AtelClient(live).raw(17100)
    copy("atel", "telegram", {"read": 17100})
    AstroNoteClient(live).listing_raw(0)
    copy("astronote", "listing", {"page": 0})
    # BTS: trimmed copy of the snapshot (header + probe rows + a deterministic sample incl. unclassified rows).
    rcfg, _ = load_config("configs/replay/replay.yaml")
    params = {"snapshot_date": str(rcfg["bts_snapshot_date"]), **UNFILTERED_PARAMS}
    raw = live.get("bts", "explorer_csv", params)
    df = pd.read_csv(io.StringIO(raw.lstrip()), dtype=str, keep_default_na=False)
    keep = pd.concat([df[df["ZTFID"] == PROBE], df.iloc[:: max(1, len(df) // BTS_FIXTURE_OIDS_EXTRA)]]).drop_duplicates()
    buf = io.StringIO()
    keep.to_csv(buf, index=False)
    copy("bts", "explorer_csv", params, "\n" + buf.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
