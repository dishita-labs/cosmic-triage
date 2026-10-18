"""First vertical slice (ARCHITECTURE §10.4, §13.7): Snapshot(t) → stub belief → Orchestrator.run → tools → validated
claims → reward delta via ClaimEffects → Trace JSONL (rendered by the console's Investigations view).

Exploratory only: nothing printed here is a benchmark claim. Paid slots stay off unless flagged *and* approved.
Usage: uv run python scripts/demo_investigate.py <OID> <MJD> [--seed 0] [--offline] [--objective O1]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import asdict

from cosmic_triage.belief.stub import fink_stub_belief
from cosmic_triage.contracts import Objective
from cosmic_triage.ingest import AlerceClient, Cache, FinkClient, LasairClient, TNSClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.ingest.catalogs import SimbadClient
from cosmic_triage.ingest.models import ClaudeClient, JevClient
from cosmic_triage.investigator.config import InvestigatorConfig
from cosmic_triage.investigator.factory import Clients, build_orchestrator
from cosmic_triage.investigator.io import write_run
from cosmic_triage.replay.clock import Clock
from cosmic_triage.replay.pool import ForwardPool
from cosmic_triage.settings import PROJECT_ROOT, load_config
from cosmic_triage.spend import SpendGuard
from cosmic_triage.value.claim_effects import ClaimEffects


def objective(oid: str = "O1") -> Objective:
    cfg, _ = load_config("configs/objectives/objectives.yaml")
    o = cfg[oid]
    return Objective(id=oid, name=o["name"], description=o["description"], reward_table=o["reward_table"])  # type: ignore[arg-type]


def make_clients(cache: Cache, cfg: InvestigatorConfig) -> Clients:
    guard = SpendGuard()
    return Clients(alerce=AlerceClient(cache), lasair=LasairClient(cache), tns=TNSClient(cache), simbad=SimbadClient(cache),
                   claude=ClaudeClient(cache, guard, cfg.models["claude_extractor"]), jev=JevClient(cache, guard, cfg.models["jev"]))


def blocked_notes(cfg: InvestigatorConfig) -> list[str]:
    notes = []
    if not TNSClient.credentials_present():
        notes.append("TNS report dates: BLOCKED: CREDENTIAL REQUIRED (TNS_BOT_ID/NAME/API_KEY) — using the approved Lasair-TNS "
                     "fallback (discovery only) + Fink d:tns as evidence_by; neither is Tier-A truth")
    guard = SpendGuard()
    for flag in ("claude_extractor", "jev_gate", "jev_verifier"):
        if cfg.flags[flag] and not guard.approved:
            notes.append(f"{flag}: flagged on but BLOCKED: SPEND NOT APPROVED — calls refused by SpendGuard, logged")
        elif not cfg.flags[flag]:
            notes.append(f"{flag}: off (configs/investigator/investigator.yaml)")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oid")
    ap.add_argument("mjd", type=float)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--objective", default="O1")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    t0 = time.time()
    cache = Cache()
    cfg = InvestigatorConfig.load()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache), workers=4)
    snap = Clock().snapshot(args.mjd, pool)
    if args.oid not in {c.oid for c in snap.candidates}:
        print(f"{args.oid} is not in the forward pool at t={args.mjd} ({len(snap.candidates)} members)")
        return 2
    cand = next(c for c in snap.candidates if c.oid == args.oid)
    belief = fink_stub_belief(cand)
    orch = build_orchestrator(make_clients(cache, cfg), cfg)
    res = orch.run(args.oid, snap, objective(args.objective), belief, seed=args.seed)
    factor, effects = ClaimEffects().apply(res.ledger.claims)
    path = write_run(res, PROJECT_ROOT / "runs", {"effects": {"spectrum_reward_factor": factor, "log": [asdict(e) for e in effects]},
                                                   "belief_stub": {k: round(v, 4) for k, v in belief.probs.items()},
                                                   "blocked": blocked_notes(cfg)})
    print(f"== {res.oid} at t={res.t_mjd:.4f} ({res.night_id}) · run {res.run_id} · EXPLORATORY")
    print(f"stub belief (Fink scores, uncalibrated): {', '.join(f'{k} {v:.2f}' for k, v in belief.probs.items())}; "
          f"entropy {belief.entropy_nats:.2f} nats")
    for s in res.trace.spans:
        extra = s.attrs.get("reason") or s.attrs.get("stop_reason") or s.error or ""
        if s.kind == "tool" and s.status == "ok":
            extra = f"{s.attrs.get('new_evidence')} new evidence, {s.attrs.get('filtered_post_t')} filtered post-t"
        if s.kind == "validator":
            extra = "accepted" if s.attrs.get("accepted") else "rejected: " + "; ".join(
                f"{c['name']}" for c in s.attrs["checks"] if not c["passed"])
        print(f"  [{s.span_id}] {s.kind:9s} {s.name:22s} {s.status:7s} {extra}")
    print(f"outcome: {res.outcome} (stop: {res.stop_reason}); {len(res.ledger.claims)} validated claim(s), "
          f"{len(res.rejected)} rejected draft(s); cost ${res.trace.cost_usd:.4f}")
    for c in res.ledger.claims:
        print(f"  ✓ {c.kind}: {c.payload}")
    print(f"ClaimEffects: spectrum reward factor 1.0 → {factor} (Δ = {factor - 1.0:+.2f} × R); "
          + "; ".join(f"{e.claim_kind}={e.status}" for e in effects))
    for n in blocked_notes(cfg):
        print(f"  note: {n}")
    print(f"trace: {path.relative_to(PROJECT_ROOT)} · output hash {res.output_hash[:16]} · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
