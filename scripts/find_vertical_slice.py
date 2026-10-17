"""Pick the §10.4 / §13.7 vertical-slice object: a BTS-classified 2025 SN Ia with a Sherlock host match and a TNS
classification. Prefers objects in an M1 pool night (so the console and Theater can show it) and pre-peak at t.

Evidence sources: BTS catalog (type, IAU name, peak), Lasair Sherlock (host), Lasair crossmatch_tns (TNS type;
TNS bot access is credential-blocked, kill-test #1), Fink alert-time d:tns (when the TNS class first appeared).
Writes runs/m1/vertical_slice.json. Never invents an OID: if nothing qualifies, records that.
"""

from __future__ import annotations

import json
import sys

from cosmic_triage.ingest import AlerceClient, Cache, FinkClient, LasairClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.replay.pool import ForwardPool, night_t
from cosmic_triage.settings import PROJECT_ROOT, load_config

MAX_LASAIR_CHECKS = 8


def main() -> int:
    rcfg, _ = load_config("configs/replay/replay.yaml")
    cache = Cache()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache))
    bts = BTSCatalog(cache)
    bts.load(str(rcfg["bts_snapshot_date"]))
    las = LasairClient(cache)
    # Candidates in the M1 pools first (pre-peak at t preferred), then any 2025 BTS SN Ia.
    seen: dict[str, dict[str, object]] = {}
    for night in rcfg["m1_nights"]:
        t = night_t(night, float(rcfg["decision_time_utc_hour"]))
        for oid in pool.candidates(t):
            r = bts.row(oid)
            if r is None or str(r["type"]).strip() != "SN Ia" or not str(r["IAUID"]).startswith("SN2025"):
                continue
            peak = r.get("peak_mjd")
            info = seen.setdefault(oid, {"oid": oid, "iau": r["IAUID"], "peakmag": r["peakmag_f"], "peak_mjd": peak,
                                         "nights": [], "pre_peak_nights": []})
            info["nights"].append(night)  # type: ignore[union-attr]
            if peak is not None and t < float(peak):
                info["pre_peak_nights"].append(night)  # type: ignore[union-attr]
    ranked = sorted(seen.values(), key=lambda x: (-len(x["pre_peak_nights"]), float(x["peakmag"] or 99)))  # type: ignore[arg-type]
    print(f"{len(ranked)} BTS 'SN Ia' (SN2025*) objects in the M1 pools; checking Sherlock + TNS for up to {MAX_LASAIR_CHECKS}")
    checked = []
    chosen = None
    for c in ranked[:MAX_LASAIR_CHECKS]:
        oid = str(c["oid"])
        sher = las.sherlock_object(oid)
        tns = las.tns_crossmatch(oid)
        host = [s for s in sher if s.get("classification") == "SN" and s.get("catalogue_object_id")]
        tns_ia = [x for x in tns if str(x.get("type") or "").startswith("SN Ia")]
        fink = FinkClient(cache).object_rows(oid, with_upperlim=False)
        first_tns = min((r["i:jd"] - 2400000.5 for r in fink if str(r.get("d:tns") or "").startswith("SN Ia")), default=None)
        rec = {**c, "sherlock": [{k: s.get(k) for k in ("classification", "catalogue_object_id", "catalogue_table_name",
                                                         "separationArcsec", "z", "photoZ", "association_type")} for s in sher],
               "tns": [{k: x.get(k) for k in ("tns_prefix", "tns_name", "type", "disc_date", "z")} for x in tns],
               "fink_first_alert_with_tns_SN_Ia_mjd": first_tns,
               "qualifies": bool(host and tns_ia)}
        checked.append(rec)
        print(f"  {oid} {c['iau']} peak {c['peakmag']}: host={bool(host)} tns_ia={bool(tns_ia)} pre-peak nights={c['pre_peak_nights']}")
        if rec["qualifies"] and chosen is None:
            chosen = rec
            break
    out = {"chosen": chosen, "checked": checked, "criteria": "BTS type == 'SN Ia' and IAU name SN2025*; Lasair Sherlock "
           "classification SN with a catalogued host; Lasair crossmatch_tns type SN Ia; in an M1 pool night",
           "caveat": "TNS classification verified through Lasair's TNS crossmatch (TNS bot credentials not configured)."}
    (PROJECT_ROOT / "runs" / "m1" / "vertical_slice.json").write_text(json.dumps(out, indent=1, default=str))
    print("chosen:", chosen["oid"] if chosen else "NONE — documented, not invented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
