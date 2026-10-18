"""M1.1 bright-regime recall diagnostic (ARCHITECTURE §10.3 M1.1). Writes runs/m1/m1.1/recall_bright.{md,json}.

Replay-side script (reads BTS truth and object-level final aggregates; nothing here reaches a Snapshot).
Denominator per night t: BTS objects with peak <= 18.5 (scored regime), saved by t (savedate <= t), whose ALeRCE first
detection lies inside the forward window [t - 14 d, t]. Numerator: those that reached the forward pool at t.
Every miss is attributed to the stage that dropped it — the superset (necessary conditions on final aggregates) or
the time-honest pre-filter at t — with its reasons and the facts behind them.
Usage: uv run python scripts/recall_bright.py [--offline]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any

from cosmic_triage.ingest import AlerceClient, Cache, FinkClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient, objects_by_oid
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.replay.pool import ForwardPool, RawCandidate, evaluate, galactic_b, night_t, normalise_alerce_lightcurve
from cosmic_triage.settings import PROJECT_ROOT, load_config

OUT = PROJECT_ROOT / "runs" / "m1" / "m1.1"


def superset_reasons(obj: dict[str, Any] | None, cfg: Any) -> list[str]:
    if obj is None:
        return ["superset:not_in_alerce_db"]
    r = []
    if (obj["ndet"] or 0) < cfg.min_detections:
        r.append("superset:final_ndet_lt_min")
    if obj["magmin"] is None or obj["magmin"] > cfg.max_mag:
        r.append("superset:alltime_brightest_fainter_than_max_mag")
    if not obj["any_nonstellar_ps1"]:
        r.append("superset:every_ps1_row_star_like")
    if obj["meanra"] is None or abs(galactic_b(obj["meanra"], obj["meandec"])) <= cfg.min_abs_gal_b - 0.5:
        r.append("superset:galactic_plane_margin")
    return r or ["superset:unexplained"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    rcfg, rhash = load_config("configs/replay/replay.yaml")
    cache = Cache()
    db = AlerceDBClient(cache)
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), db, workers=4)
    cfg = pool.cfg
    bts = BTSCatalog(cache)
    df = bts.load(str(rcfg["bts_snapshot_date"]))
    nights = list(rcfg["m1_nights"])
    ts = {n: night_t(n, float(rcfg["decision_time_utc_hour"])) for n in nights}
    lo, hi = min(ts.values()) - cfg.window_days - 30, max(ts.values())
    cand = df[(df["peakmag_f"].notna()) & (df["peakmag_f"] <= cfg.scored_peak_mag) & df["savedate_mjd"].notna()]
    cand = cand[(cand["savedate_mjd"] >= lo) & (cand["savedate_mjd"] <= hi)]
    objs = {o["oid"]: o for o in objects_by_oid(db, sorted(cand["ZTFID"]), cfg.star_min_sgscore, cfg.star_max_dist)}
    rows: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    for n in nights:
        t = ts[n]
        sup = pool.superset(t)
        res = pool.evaluate_all(t)
        denom = []
        for r in cand.itertuples(index=False):
            oid = str(r.ZTFID)
            o = objs.get(oid)
            if r.savedate_mjd > t or o is None or o["firstmjd"] is None or not (t - cfg.window_days <= o["firstmjd"] <= t):
                if o is None and r.savedate_mjd <= t:
                    misses.append({"night": n, "oid": oid, "stage": "superset", "reasons": ["superset:not_in_alerce_db"]})
                continue
            denom.append((oid, r))
        reached = 0
        for oid, r in denom:
            if oid in res and res[oid].passed:
                reached += 1
                continue
            stage = "prefilter" if oid in sup else "superset"
            if stage == "prefilter":
                raw = pool.raw(oid)
                fr = res[oid]
                reasons = list(fr.reasons)
            else:
                # Outside the superset: the superset's own necessary-condition failures are the attribution. The
                # extra at-t evaluation uses ALeRCE only (no Fink rows: no per-alert history / Fink star context).
                dets, nds = normalise_alerce_lightcurve(pool.alerce.lightcurve(oid), pool.deny)
                raw = RawCandidate(oid, dets, nds, [], {})
                fr = evaluate(raw, t, cfg)
                reasons = superset_reasons(objs.get(oid), cfg) + [f"(ALeRCE-only at t: {x})" for x in fr.reasons]
            all_q = [float(d["magpsf"]) for d in raw.detections
                     if d.get("drb") is not None and float(d["drb"]) >= cfg.min_drb and str(d.get("isdiffpos")).lower() in ("1", "t", "true")]
            misses.append({
                "night": n, "oid": oid, "stage": stage, "reasons": reasons, "bts_type": str(r.type).strip(),
                "bts_peakmag": r.peakmag_f, "bts_peak_mjd": r.peak_mjd, "savedate_mjd": r.savedate_mjd,
                "alerce_firstmjd": objs[oid]["firstmjd"], "brightest_qualifying_at_t": fr.brightest_mag,
                "n_hist_at_t": fr.n_hist, "first_detection_at_t": fr.first_detection_mjd,
                "first_from_alert_history": fr.first_from_alert_history,
                "brightest_qualifying_ever": min(all_q) if all_q else None,
                "peak_after_t": r.peak_mjd is not None and r.peak_mjd > t,
            })
        rows.append({"night": n, "t_mjd": t, "denominator": len(denom), "reached_pool": reached,
                     "denominator_oids": sorted(o for o, _ in denom),
                     "recall": reached / len(denom) if denom else None})
        print(f"{n}: BTS bright saved-by-t in window {len(denom)}, reached pool {reached}")
    tot_d = sum(r["denominator"] for r in rows)
    tot_r = sum(r["reached_pool"] for r in rows)
    out = {"nights": rows, "total_denominator": tot_d, "total_reached": tot_r, "recall": tot_r / tot_d if tot_d else None,
           "misses": misses, "prefilter_hash": cfg.config_hash, "replay_hash": rhash,
           "miss_reasons": dict(Counter(x for m in misses for x in m["reasons"] if not x.startswith("("))),
           "unique_missed_objects": sorted({m["oid"] for m in misses})}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "recall_bright.json").write_text(json.dumps(out, indent=1, default=float))
    L = [
        "# M1.1 bright-regime recall diagnostic",
        "",
        f"Denominator per night t: BTS objects with peak ≤ {cfg.scored_peak_mag} saved by t whose ALeRCE first detection is in "
        f"[t − {cfg.window_days:g} d, t]. Pre-filter `{cfg.config_hash}` (v{cfg.version}). Replay-side diagnostic (reads truth).",
        "",
        "| Night | Denominator | Reached pool | Recall |",
        "|---|---|---|---|",
    ]
    for r in rows:
        L.append(f"| {r['night']} | {r['denominator']} | {r['reached_pool']} | "
                 f"{'—' if r['recall'] is None else f'{100 * r['recall']:.1f}%'} |")
    L += [f"| **all** | **{tot_d}** | **{tot_r}** | **{100 * tot_r / tot_d:.1f}%** |" if tot_d else "", "",
          "## Misses (object-night pairs)", "",
          "| Night | OID | Stage | Reasons | BTS type | BTS peak (mjd) | Saved | Brightest qual. at t | Brightest qual. ever | n_hist at t |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for m in misses:
        if "bts_type" not in m:
            L.append(f"| {m['night']} | {m['oid']} | {m['stage']} | {', '.join(m['reasons'])} | | | | | | |")
            continue
        f = lambda v, p=2: "—" if v is None else f"{v:.{p}f}"  # noqa: E731
        L.append(f"| {m['night']} | {m['oid']} | {m['stage']} | {', '.join(m['reasons'])} | {m['bts_type']} | "
                 f"{f(m['bts_peakmag'])} ({f(m['bts_peak_mjd'], 1)}) | {f(m['savedate_mjd'], 1)} | "
                 f"{f(m['brightest_qualifying_at_t'])} | {f(m['brightest_qualifying_ever'])} | {m['n_hist_at_t']} |")
    L += ["", f"Miss reasons (counts over object-nights): {out['miss_reasons']}"]
    (OUT / "recall_bright.md").write_text("\n".join(L) + "\n")
    print(f"recall {tot_r}/{tot_d}; misses {len(misses)} object-nights, {len(out['unique_missed_objects'])} objects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
