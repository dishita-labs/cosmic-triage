"""M1 pool statistics + budget-binding check (ARCHITECTURE §6.3, §10.3 M1). Writes runs/m1/pool_stats.{md,json}.

Replay-side script: it may read BTS truth (labels are reported as pool composition, never fed back).
Bright SN-like (time-honest, at t): pool member, brightest qualifying magnitude <= 18.5 at t, and latest alert-time
Fink SIMBAD crossmatch not stellar/AGN. Budget rule: largest B with median(bright SN-like)/B >= 2.
Usage: uv run python scripts/pool_stats.py [--offline]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter

from cosmic_triage.ingest import AlerceClient, Cache, FinkClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.replay.labels import ClassMap, label_candidate
from cosmic_triage.replay.pool import ForwardPool, night_t
from cosmic_triage.settings import PROJECT_ROOT, load_config

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from m0_killtests import sn_like


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    rcfg, rhash = load_config("configs/replay/replay.yaml")
    fcfg, _ = load_config("configs/facilities/palomar_sedm.yaml")
    cache = Cache()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache))
    bts = BTSCatalog(cache)
    bts.load(str(rcfg["bts_snapshot_date"]))
    cmap = ClassMap()
    scored = pool.cfg.scored_peak_mag
    rows = []
    for night in rcfg["m1_nights"]:
        t = night_t(night, float(rcfg["decision_time_utc_hour"]))
        res = pool.evaluate_all(t)
        members = sorted(o for o, r in res.items() if r.passed)
        bright = [o for o in members if (res[o].brightest_mag or 99) <= scored]
        bright_sn = [o for o in bright if sn_like(pool.raw(o), t)]
        labels = {o: label_candidate(o, pool.raw(o), bts, cmap, scored) for o in members}
        lab = Counter(lb.label or "unscored" for lb in labels.values())
        cls = Counter(lb.coarse_class for lb in labels.values() if lb.label == "class")
        # Recall vs BTS: objects BTS saved by t whose first detection (<= t) is inside the window.
        saved_by_t = []
        for oid, raw in ((o, pool.raw(o)) for o in res):
            r = bts.row(oid)
            if r is None or r.get("savedate_mjd") is None or r["savedate_mjd"] > t:
                continue
            dets = raw.dets_le(t)
            if not dets or min(d["mjd"] for d in dets) < t - pool.cfg.window_days:
                continue  # outside the forward window by definition
            saved_by_t.append(oid)
        missed = [o for o in saved_by_t if not res[o].passed]
        rows.append({
            "night": night, "t_mjd": t, "superset": len(res), "pool": len(members), "bright_le_18p5_at_t": len(bright),
            "bright_sn_like": len(bright_sn), "labels": dict(lab), "classes": dict(cls),
            "bts_saved_by_t_in_superset": len(saved_by_t), "bts_saved_by_t_in_pool": len(saved_by_t) - len(missed),
            "bts_missed_reasons": dict(Counter(x for o in missed for x in res[o].reasons)),
            "rejection_reasons": dict(Counter(x for o, r in res.items() if not r.passed for x in r.reasons)),
        })
        print(f"{night}: superset {len(res)} pool {len(members)} bright {len(bright)} bright SN-like {len(bright_sn)} labels {dict(lab)}")
    med = statistics.median(r["bright_sn_like"] for r in rows)
    ratios = {b: med / b for b in range(1, max(13, int(med) + 1))}
    bmax = max((b for b, q in ratios.items() if q >= 2), default=0)
    out = {"nights": rows, "median_bright_sn_like": med, "ratios": ratios, "budget_max_binding": bmax,
           "prefilter_hash": pool.cfg.config_hash, "replay_hash": rhash, "scored_peak_mag": scored}
    (PROJECT_ROOT / "runs" / "m1").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "runs" / "m1" / "pool_stats.json").write_text(json.dumps(out, indent=1))
    L = [
        "# M1 forward-pool statistics and budget-binding check",
        "",
        f"Nights: {', '.join(rcfg['m1_nights'])} (decision time t = local date 20:00 UTC). Pre-filter `{pool.cfg.config_hash}` "
        f"(configs/replay/prefilter.yaml v{pool.cfg.version}); BTS snapshot {rcfg['bts_snapshot_date']}. All pool counts use data <= t only. "
        "Labels use BTS truth (replay-only) and are shown as composition, never fed to any decision.",
        "",
        "| Night | Window superset | Pool (pre-filter at t) | Bright (≤ 18.5 at t) | Bright SN-like | class | unknown | contaminant "
        "| unscored | BTS saved by t: in pool / in superset |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lb = r["labels"]
        L.append(f"| {r['night']} | {r['superset']} | {r['pool']} | {r['bright_le_18p5_at_t']} | {r['bright_sn_like']} | "
                 f"{lb.get('class', 0)} | {lb.get('unknown', 0)} | {lb.get('contaminant', 0)} | {lb.get('unscored', 0)} | "
                 f"{r['bts_saved_by_t_in_pool']} / {r['bts_saved_by_t_in_superset']} |")
    L += [
        "",
        "## Budget-binding check (§6.3)",
        "",
        f"Rule: choose the spectra-per-night budget B so that median(bright SN-like candidates) / B ≥ 2; if the sky does not "
        f"supply enough, shrink B (3–4/night), never inflate the pool. Median bright SN-like = **{med}**.",
        "",
        "| B (spectra/night) | median / B | binds (≥ 2)? |",
        "|---|---|---|",
    ]
    for b in range(2, 11):
        L.append(f"| {b} | {ratios[b]:.2f} | {'yes' if ratios[b] >= 2 else 'no'} |")
    L += [
        "",
        f"**Largest binding budget: B = {bmax} spectra/night.** "
        + ("The architecture's floor (3–4/night) is satisfied." if bmax >= 3 else
           "Below the architecture's 3–4/night floor: **Needs architecture decision** (§14.7, kill-test #4 fallback)."),
        f"Facility: {fcfg['id']} (overhead {fcfg['overhead_s']} s, min altitude {fcfg['min_altitude_deg']}°, moon sep {fcfg['min_moon_sep_deg']}°).",
        "",
        "## Composition",
        "",
    ]
    for r in rows:
        L.append(f"- **{r['night']}** coarse classes among BTS-classified pool members: {r['classes'] or '—'}; "
                 f"rejection reasons in superset: {r['rejection_reasons']}; BTS-saved-by-t objects rejected at t: {r['bts_missed_reasons'] or 'none'}")
    L += ["", "Definitions: *bright SN-like* = pool member whose brightest qualifying detection at t is ≤ 18.5 mag and whose latest "
          "alert-time Fink SIMBAD crossmatch is not a stellar/AGN type (`scripts/m0_killtests.py:SN_LIKE_CDS_EXCLUDE`). "
          "*BTS saved by t* = in BTS with savedate ≤ t and first detection (≤ t) inside the 14-day window (recall diagnostic for the time-honest filter)."]
    (PROJECT_ROOT / "runs" / "m1" / "pool_stats.md").write_text("\n".join(L) + "\n")
    print(f"median bright SN-like {med}; largest binding budget {bmax}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
