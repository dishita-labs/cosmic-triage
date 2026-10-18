"""M1.1: second and third vertical-slice objects (ARCHITECTURE §10.3 M1.1). Writes runs/m1/m1.1/vertical_slices.json.

2. Already-classified-at-t SN: a BTS-classified SN pool member at night t whose Fink alert-time ``d:tns`` already
   carried an SN class at an alert <= t. This is ``evidence_by`` (the classification existed by that alert). The
   TNS *report date* cannot be checked (TNS bot credentials pending; kill-test #1), so it is never treated as truth.
3. AGN contaminant: a pool member labelled contaminant (provisional, §6.4) with AGN context at t — Fink alert-time
   SIMBAD crossmatch of an AGN type and/or a Lasair Sherlock AGN classification (static). If no *contaminant*-labelled
   member has AGN context, the fallback tier is any non-classified member (unknown / unscored) with Sherlock AGN or NT,
   and the chosen object's label is recorded as-is (never relabelled).
Replay-side script (reads BTS truth). Never invents an OID: if nothing qualifies, records that.
Usage: uv run python scripts/find_vertical_slices_m1_1.py [--offline]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from cosmic_triage.ingest import AlerceClient, Cache, FinkClient, LasairClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.ingest.errors import CredentialMissing, OfflineCacheMiss
from cosmic_triage.replay.labels import ClassMap, label_candidate
from cosmic_triage.replay.pool import ForwardPool, night_t
from cosmic_triage.settings import PROJECT_ROOT, load_config

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from labels_audit import AGN_CDS

OUT = PROJECT_ROOT / "runs" / "m1" / "m1.1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    rcfg, _ = load_config("configs/replay/replay.yaml")
    cache = Cache()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache), workers=4)
    bts = BTSCatalog(cache)
    bts.load(str(rcfg["bts_snapshot_date"]))
    cmap = ClassMap()
    classified: list[dict[str, Any]] = []
    agn: list[dict[str, Any]] = []
    for n in rcfg["m1_nights"]:
        t = night_t(n, float(rcfg["decision_time_utc_hour"]))
        for oid in pool.candidates(t):
            raw = pool.raw(oid)
            lab = label_candidate(oid, raw, bts, cmap, pool.cfg.scored_peak_mag, pool.cfg.min_drb)
            rows = raw.fink_le(t)
            tns = next((r for r in rows if str(r.get("d:tns") or "").startswith("SN")), None)
            if lab.label == "class" and lab.coarse_class in ("Ia", "II", "Ibc") and tns is not None:
                classified.append({"oid": oid, "night": n, "t_mjd": t, "bts_type": lab.bts_type, "bts_peakmag": lab.peak_mag,
                                   "fink_tns_label": tns["d:tns"], "evidence_by_mjd": tns["mjd"],
                                   "days_classified_before_t": t - tns["mjd"],
                                   "label_matches_bts": str(tns["d:tns"]).strip() == str(lab.bts_type).strip()})
            cds = str(rows[-1].get("d:cdsxmatch") or "") if rows else ""
            if lab.label != "class" and oid not in {a["oid"] for a in agn}:
                agn.append({"oid": oid, "night": n, "t_mjd": t, "label": lab.label or "unscored", "fink_cdsxmatch_at_t": cds,
                            "qualifying_peak": lab.peak_mag})
    # Sherlock context for the AGN candidates (static; batched).
    sherlock: dict[str, dict[str, Any]] = {}
    status = "ok"
    try:
        las = LasairClient(cache)
        ids = sorted({a["oid"] for a in agn})
        las.prefetch(ids, "sherlock_classifications")
        sherlock = {o: rows[0] for o in ids if (rows := las.sherlock_object(o))}
    except (CredentialMissing, OfflineCacheMiss) as exc:
        status = f"unavailable: {type(exc).__name__}"
    for a in agn:
        s = sherlock.get(a["oid"], {})
        a["sherlock_class"] = s.get("classification")
        a["sherlock_sep_arcsec"] = s.get("separationArcsec")
        a["sherlock_catalogue"] = s.get("catalogue_table_name")
        a["tier"] = ("contaminant + AGN context" if a["label"] == "contaminant" and (a["fink_cdsxmatch_at_t"] in AGN_CDS
                                                                                     or a["sherlock_class"] == "AGN")
                     else "fallback: non-classified + AGN/NT context" if a["sherlock_class"] in ("AGN", "NT")
                     or a["fink_cdsxmatch_at_t"] in AGN_CDS else None)
    agn = [a for a in agn if a["tier"]]
    # Prefer: matching label, classified longest before t, bright; AGN: Sherlock agrees, then nuclear.
    classified.sort(key=lambda c: (not c["label_matches_bts"], -c["days_classified_before_t"], c["bts_peakmag"] or 99))
    agn.sort(key=lambda a: (a["tier"] != "contaminant + AGN context", a.get("sherlock_class") != "AGN",
                            a.get("sherlock_sep_arcsec") or 99, a["qualifying_peak"] or 99))
    out = {
        "already_classified_sn": {"chosen": classified[0] if classified else None, "n_candidates": len(classified),
                                  "candidates": classified[:10],
                                  "criteria": "BTS-classified SN (Ia/II/Ibc) in a pool at t; Fink d:tns = SN* at an alert <= t",
                                  "caveat": "date_kind = evidence_by (tool evidence, never Tier-A truth); TNS report date "
                                            "BLOCKED: CREDENTIAL REQUIRED (TNS bot registration pending)"},
        "agn_contaminant": {"chosen": agn[0] if agn else None, "n_candidates": len(agn), "candidates": agn[:10],
                            "criteria": "tier 1: contaminant label (provisional) + AGN context (Fink alert-time cdsxmatch "
                                        "AGN-type or Sherlock AGN); tier 2 fallback: unknown/unscored member with Sherlock AGN/NT",
                            "n_tier1": sum(a["tier"] == "contaminant + AGN context" for a in agn),
                            "sherlock_status": status},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "vertical_slices.json").write_text(json.dumps(out, indent=1, default=float))
    for k, v in out.items():
        c = v["chosen"]
        print(f"{k}: {c['oid'] + ' @ ' + c['night'] if c else 'NONE — documented, not invented'} ({v['n_candidates']} candidates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
