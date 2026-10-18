"""M2 exploratory batch (ARCHITECTURE §10.3 M2): the Investigator on 20 candidates at chosen t — 10 BTS-classified,
10 contaminant/unknown — drawn from the M1.1 forward pools with a fixed seed (vertical-slice objects forced in).

Replay-side runner: it reads BTS labels only to *select* the strata and writes them to runs/exploratory/m2/selection.json,
never into a trace. Every run is exploratory (§10.1) and never feeds a benchmark table.
Usage: uv run python scripts/run_m2.py [--seed 20261018] [--offline]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import asdict
from typing import Any

from cosmic_triage.belief.stub import fink_stub_belief
from cosmic_triage.contracts import Snapshot
from cosmic_triage.ingest import AlerceClient, Cache, FinkClient, LasairClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.ingest.errors import CredentialMissing, OfflineCacheMiss
from cosmic_triage.investigator.config import InvestigatorConfig
from cosmic_triage.investigator.factory import build_orchestrator
from cosmic_triage.investigator.io import write_run
from cosmic_triage.replay.clock import Clock
from cosmic_triage.replay.labels import ClassMap, label_candidate
from cosmic_triage.replay.pool import ForwardPool, night_t
from cosmic_triage.settings import PROJECT_ROOT, load_config
from cosmic_triage.value.claim_effects import ClaimEffects

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from demo_investigate import blocked_notes, make_clients, objective

OUT = PROJECT_ROOT / "runs" / "exploratory" / "m2"


def forced() -> list[tuple[str, str | None, str]]:
    """(oid, preferred night, why) for the three vertical-slice objects."""
    out: list[tuple[str, str | None, str]] = []
    vs1 = PROJECT_ROOT / "runs" / "m1" / "vertical_slice.json"
    if vs1.exists() and (c := json.loads(vs1.read_text())["chosen"]):
        out.append((c["oid"], c["pre_peak_nights"][-1] if c["pre_peak_nights"] else None, "vertical slice 1 (SN Ia, host, TNS)"))
    vs = PROJECT_ROOT / "runs" / "m1" / "m1.1" / "vertical_slices.json"
    if vs.exists():
        d = json.loads(vs.read_text())
        for key, why in (("already_classified_sn", "vertical slice 2 (classified before t)"), ("agn_contaminant", "vertical slice 3 (AGN)")):
            if c := d[key]["chosen"]:
                out.append((c["oid"], c["night"], why))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261018)
    ap.add_argument("--n-per-stratum", type=int, default=10)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    t_start = time.time()
    rcfg, _ = load_config("configs/replay/replay.yaml")
    cache = Cache()
    cfg = InvestigatorConfig.load()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache), workers=4)
    bts = BTSCatalog(cache)
    bts.load(str(rcfg["bts_snapshot_date"]))
    cmap = ClassMap()
    clock = Clock()
    snaps: dict[str, Snapshot] = {}
    members: dict[str, dict[str, dict[str, Any]]] = {}  # night -> oid -> label info
    for n in rcfg["m1_nights"]:
        snaps[n] = clock.snapshot(night_t(n, float(rcfg["decision_time_utc_hour"])), pool)
        members[n] = {}
        for c in snaps[n].candidates:
            lab = label_candidate(c.oid, pool.raw(c.oid), bts, cmap, pool.cfg.scored_peak_mag, pool.cfg.min_drb)
            members[n][c.oid] = {"label": lab.label, "coarse_class": lab.coarse_class, "bts_type": lab.bts_type}
    rng = random.Random(args.seed)
    chosen: list[dict[str, Any]] = []
    taken: set[str] = set()

    def stratum(info: dict[str, Any]) -> str | None:
        return "bts_classified" if info["label"] == "class" else ("contaminant_or_unknown" if info["label"] in ("contaminant", "unknown") else None)

    for oid, night, why in forced():
        nights = [night] if night and oid in members.get(night, {}) else [n for n in members if oid in members[n]]
        if nights and stratum(members[nights[0]][oid]):
            chosen.append({"oid": oid, "night": nights[0], "why": why, **members[nights[0]][oid],
                           "stratum": stratum(members[nights[0]][oid])})
            taken.add(oid)
    for s in ("bts_classified", "contaminant_or_unknown"):
        pool_s = sorted({(o, n) for n in members for o, i in members[n].items() if stratum(i) == s and o not in taken})
        by_oid: dict[str, list[str]] = {}
        for o, n in pool_s:
            by_oid.setdefault(o, []).append(n)
        need = args.n_per_stratum - sum(1 for c in chosen if c["stratum"] == s)
        for o in rng.sample(sorted(by_oid), max(0, min(need, len(by_oid)))):
            n = rng.choice(by_oid[o])
            chosen.append({"oid": o, "night": n, "why": "random", **members[n][o], "stratum": s})
            taken.add(o)
    las = LasairClient(cache)
    try:
        for table in ("sherlock_classifications", "crossmatch_tns"):
            las.prefetch([c["oid"] for c in chosen], table)
    except (CredentialMissing, OfflineCacheMiss) as exc:
        print(f"Lasair prefetch unavailable ({type(exc).__name__}); tools will report it per run")
    orch = build_orchestrator(make_clients(cache, cfg), cfg)
    effects = ClaimEffects()
    obj = objective("O1")
    runs = []
    for c in chosen:
        snap = snaps[c["night"]]
        cand = next(x for x in snap.candidates if x.oid == c["oid"])
        t0 = time.time()
        res = orch.run(c["oid"], snap, obj, fink_stub_belief(cand), seed=0)
        factor, log = effects.apply(res.ledger.claims)
        path = write_run(res, PROJECT_ROOT / "runs", {"effects": {"spectrum_reward_factor": factor, "log": [asdict(e) for e in log]},
                                                       "blocked": blocked_notes(cfg), "batch": "m2"})
        runs.append({"oid": c["oid"], "night": c["night"], "stratum": c["stratum"], "run_id": res.run_id,
                     "trace": str(path.relative_to(PROJECT_ROOT)), "outcome": res.outcome, "stop_reason": res.stop_reason,
                     "within_budget": res.within_budget, "n_claims": len(res.ledger.claims),
                     "claim_kinds": sorted(k.kind for k in res.ledger.claims), "n_rejected": len(res.rejected),
                     "tool_errors": res.tool_errors, "spectrum_reward_factor": factor, "output_hash": res.output_hash,
                     "wall_s": round(time.time() - t0, 2), "counters": res.counters})
        print(f"{c['oid']} {c['night']} [{c['stratum']}] → {res.outcome} ({res.stop_reason}); claims "
              f"{runs[-1]['claim_kinds']}; errors {list(res.tool_errors)}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "selection.json").write_text(json.dumps({"seed": args.seed, "selected": chosen}, indent=1, default=str))
    ok = sum(1 for r in runs if r["n_claims"] or r["outcome"] == "no_context_found")
    summary = {"n_runs": len(runs), "within_budget": sum(r["within_budget"] for r in runs), "claims_or_no_context": ok,
               "outcomes": {o: sum(r["outcome"] == o for r in runs) for o in ("claims", "no_context_found", "gated_out")},
               "config_version": cfg.config_hash, "mode": cfg.mode, "flags": cfg.flags, "blocked": blocked_notes(cfg),
               "wall_s": round(time.time() - t_start, 1), "runs": runs}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"{len(runs)} runs; within budget {summary['within_budget']}; claims-or-no_context {ok}; {summary['wall_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
