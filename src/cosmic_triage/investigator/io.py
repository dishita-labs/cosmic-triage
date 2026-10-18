"""Trace JSONL (§13.2): one file per run under runs/{exploratory|bench}/<night>/<run_id>.jsonl, read by the console."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cosmic_triage.investigator.orchestrator.loop import RunResult


def run_lines(r: RunResult, extra: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    head = {"type": "run", "run_id": r.run_id, "oid": r.oid, "t_mjd": r.t_mjd, "night_id": r.night_id, "mode": r.trace.mode,
            "config_version": r.trace.config_version, "seed": r.seed, "outcome": r.outcome, "stop_reason": r.stop_reason,
            "within_budget": r.within_budget, "output_hash": r.output_hash, "model_ids": r.trace.model_ids,
            "cost_usd": r.trace.cost_usd, "counters": r.counters, "tool_errors": r.tool_errors, **(extra or {})}
    lines: list[dict[str, Any]] = [head]
    lines += [{"type": "span", **s.model_dump()} for s in r.trace.spans]
    lines += [{"type": "evidence", **e.model_dump()} for e in r.ledger.entries]
    lines += [{"type": "claim", **c.model_dump()} for c in r.ledger.claims]
    lines += [{"type": "rejected", **x} for x in r.rejected]
    return lines


def write_run(r: RunResult, root: Path, extra: dict[str, Any] | None = None) -> Path:
    path = root / r.trace.mode / r.night_id / f"{r.run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, sort_keys=True, default=float) + "\n" for x in run_lines(r, extra)))
    return path
