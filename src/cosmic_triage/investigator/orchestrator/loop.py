"""Code-owned Investigator loop (ARCHITECTURE §4.2): gate → plan → act → extract → validate → ledger → stop?

Hard budgets (tool calls, model calls, tokens, $, wall time) are checked before every step; stop conditions are
budget, no new information, resolved, or plan exhausted. Every run ends with an explicit outcome: ``claims``,
``no_context_found`` or ``gated_out``. Paid slots (Claude extractor, Jev gate/verifier) are exploratory: logged, never
gating acceptance in M2; a refused spend is recorded on the span and the run continues on the baselines.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from cosmic_triage.contracts import Belief, CandidateState, ClaimDraft, EvidenceLedger, Objective, Snapshot, Trace
from cosmic_triage.investigator.config import InvestigatorConfig
from cosmic_triage.investigator.extractors.claude import ClaudeStructuredExtractor
from cosmic_triage.investigator.extractors.rule import RuleExtractor
from cosmic_triage.investigator.ledger.ledger import Ledger
from cosmic_triage.investigator.routers.gate import Gate, GateDecision
from cosmic_triage.investigator.routers.planner import FixedOrderPlanner, Stop
from cosmic_triage.investigator.tools.base import ToolContext, ToolError, ToolRegistry, ToolUnavailable
from cosmic_triage.investigator.tracing import Tracer
from cosmic_triage.investigator.validators.chain import Validator, to_claim
from cosmic_triage.investigator.validators.support import JevNoulVerifier
from cosmic_triage.settings import canonical_json, sha256_hex

Outcome = Literal["claims", "no_context_found", "gated_out"]


@dataclass
class RunResult:
    run_id: str
    oid: str
    t_mjd: float
    night_id: str
    ledger: EvidenceLedger
    trace: Trace
    outcome: Outcome
    stop_reason: str
    rejected: list[dict[str, Any]]
    tool_errors: dict[str, str]
    within_budget: bool
    output_hash: str
    seed: int
    counters: dict[str, float] = field(default_factory=dict)


def run_id_for(oid: str, t_mjd: float, config_hash: str, seed: int) -> str:
    """Idempotency key (oid, t, config_version, seed)."""
    return f"inv-{oid}-{t_mjd:.5f}-{config_hash[:8]}-s{seed}"


class Orchestrator:
    def __init__(self, cfg: InvestigatorConfig, registry: ToolRegistry, gate: Gate, validator: Validator,
                 claude: ClaudeStructuredExtractor | None = None, jev_verifier: JevNoulVerifier | None = None,
                 backoff_base_s: float = 0.5) -> None:
        self.cfg = cfg
        self.registry = registry
        self.gate = gate
        self.planner = FixedOrderPlanner(cfg.order)
        self.rule = RuleExtractor()
        self.validator = validator
        self.claude = claude
        self.jev_verifier = jev_verifier
        self.backoff_base_s = backoff_base_s
        self.breaker: dict[str, int] = {}  # consecutive failures per tool, across runs in this process

    def run(self, oid: str, snapshot: Snapshot, objective: Objective, belief: Belief, seed: int = 0) -> RunResult:
        cand = next((c for c in snapshot.candidates if c.oid == oid), None)
        if cand is None:
            raise KeyError(f"{oid} is not in Snapshot(t={snapshot.t_mjd})")
        return self._run(cand, snapshot.t_mjd, snapshot.night_id, objective, belief, seed)

    def _run(self, cand: CandidateState, t: float, night_id: str, objective: Objective, belief: Belief, seed: int) -> RunResult:
        cfg, b = self.cfg, self.cfg.budgets
        run_id = run_id_for(cand.oid, t, cfg.config_hash, seed)
        rng = random.Random(f"{run_id}")
        tracer, ledger = Tracer(), Ledger(cand.oid)
        ctx = ToolContext(t, cand, run_id)
        t0 = time.perf_counter()
        n_tool = n_model = 0
        rejected: list[dict[str, Any]] = []
        tool_errors: dict[str, str] = {}
        model_ids: dict[str, str] = {}

        def model_budget_ok() -> bool:
            tin, tout, usd = tracer.totals()
            return n_model < b.max_model_calls and tin + tout < b.max_tokens and usd < b.max_usd

        # gate
        g0 = time.perf_counter()
        dec: GateDecision | None
        try:
            dec = self.gate.decide(belief, objective, run_id)
            gspan = tracer.add("gate", self.gate.name, started=g0, call=dec.call,
                               attrs={"investigate": dec.investigate, "reason": dec.reason, "score": dec.score})
            if dec.call:
                n_model += 1
                model_ids["gate"] = dec.call.model_id
        except Exception as exc:  # a paid gate refused / failed: fall back to the baseline decision recorded in the span
            base: Gate | None = getattr(self.gate, "baseline", None)
            dec = base.decide(belief, objective, run_id) if base is not None else None
            gspan = tracer.add("gate", self.gate.name, started=g0, status="error", error=f"{type(exc).__name__}: {exc}"[:300],
                               attrs={"investigate": bool(dec and dec.investigate), "reason": dec.reason if dec else "error",
                                      "fallback": getattr(base, "name", None)})
        if dec is None or not dec.investigate:
            return self._finish(run_id, cand, t, night_id, tracer, ledger, "gated_out", "gate", rejected, tool_errors, model_ids,
                                True, seed, n_tool)

        stop_reason, no_new = "plan_exhausted", 0
        attempted: set[str] = set()
        within_budget = True
        while True:
            if n_tool >= b.max_tool_calls:
                stop_reason = "budget:tool_calls"
                break
            if time.perf_counter() - t0 > b.max_wall_s:
                stop_reason, within_budget = "budget:wall_time", True
                break
            step = self.planner.next_tool(attempted, self.registry.names())
            if isinstance(step, Stop):
                stop_reason = step.reason
                break
            name = step.name
            attempted.add(name)
            tool = self.registry.get(name)
            inp = tool.build_input(ctx, ledger)
            if inp is None:
                tracer.add("tool", name, status="skipped", parent=gspan.span_id, attrs={"reason": "not applicable"})
                continue
            if self.breaker.get(name, 0) >= int(cfg.tools["circuit_breaker_failures"]):
                tracer.add("tool", name, status="skipped", parent=gspan.span_id, attrs={"reason": "circuit open"})
                tool_errors[name] = "circuit open"
                continue
            n_tool += 1
            s0 = time.perf_counter()
            retries, res, err = 0, None, None
            while True:
                try:
                    res = self.registry.run(name, inp, t)
                    self.breaker[name] = 0
                    break
                except ToolError as exc:
                    err = exc
                    if exc.retryable and retries < int(cfg.tools["max_retries"]):
                        retries += 1
                        time.sleep(self.backoff_base_s * (2 ** (retries - 1)) * (1 + rng.random()))
                        continue
                    if not isinstance(exc, ToolUnavailable):
                        self.breaker[name] = self.breaker.get(name, 0) + 1
                    break
            if res is None:
                tool_errors[name] = f"{type(err).__name__}: {err}"[:300]
                tracer.add("tool", name, started=s0, status="error", parent=gspan.span_id, error=tool_errors[name],
                           attrs={"retries": retries, "input": inp.model_dump()})
                no_new += 1
            else:
                new = [e for e in res.evidence if ledger.add(e)]
                tracer.add("tool", name, started=s0, parent=gspan.span_id, cache_hit=res.cache_hit,
                           attrs={"retries": retries, "input": _short(inp.model_dump()), "output": res.output.model_dump(),
                                  "evidence_ids": [e.id for e in res.evidence], "new_evidence": len(new),
                                  "filtered_post_t": res.filtered_post_t,
                                  "as_of": {e.id: e.source_date for e in res.evidence}})
                no_new = 0 if new else no_new + 1
                if new:
                    self._extract_validate(self.rule.draft(new, list(ledger.entries())), "rule", ledger, tracer, t, cand, run_id, rejected, gspan.span_id)
            if cfg.stop_when_resolved and any(c.kind == "prior_classification" for c in ledger.claims()):
                stop_reason = "resolved:prior_classification"
                break
            if no_new >= cfg.patience:
                stop_reason = "no_new_information"
                break

        # optional exploratory Claude pass over all evidence (reconciliation / unstructured text)
        if self.claude is not None and ledger.entries():
            if model_budget_ok():
                e0 = time.perf_counter()
                try:
                    drafts, call = self.claude.draft_with_call(list(ledger.entries()), run_id)
                    n_model += 1
                    model_ids["extractor"] = call.model_id
                    span = tracer.add("extract", "claude_structured", started=e0, call=call, parent=gspan.span_id,
                                      attrs={"n_drafts": len(drafts)})
                    self._extract_validate(drafts, "claude", ledger, tracer, t, cand, run_id, rejected, span.span_id, extracted=True)
                except Exception as exc:
                    tracer.add("extract", "claude_structured", started=e0, status="error", parent=gspan.span_id,
                               error=f"{type(exc).__name__}: {exc}"[:300])
            else:
                tracer.add("extract", "claude_structured", status="skipped", attrs={"reason": "model budget"})

        tin, tout, usd = tracer.totals()
        within_budget = within_budget and n_tool <= b.max_tool_calls and tin + tout <= b.max_tokens and usd <= b.max_usd
        outcome: Outcome = "claims" if ledger.claims() else "no_context_found"
        return self._finish(run_id, cand, t, night_id, tracer, ledger, outcome, stop_reason, rejected, tool_errors, model_ids,
                            within_budget, seed, n_tool)

    def _extract_validate(self, drafts: list[ClaimDraft], extractor: str, ledger: Ledger, tracer: Tracer, t: float,
                          cand: CandidateState, run_id: str, rejected: list[dict[str, Any]], parent: str,
                          extracted: bool = False) -> None:
        if not extracted:
            tracer.add("extract", extractor, parent=parent, attrs={"n_drafts": len(drafts),
                                                                   "kinds": sorted({d.kind for d in drafts})})
        entries = {e.id: e for e in ledger.entries()}
        for d in drafts:
            if ledger.has_claim(d):
                continue
            v0 = time.perf_counter()
            report, _ = self.validator.validate(d, entries, t, cand, run_id)
            jev_attrs: dict[str, Any] = {}
            if self.jev_verifier is not None:
                try:
                    score, call = self.jev_verifier.score(d, [entries[i] for i in d.evidence_ids if i in entries], run_id)
                    tracer.add("model", "jev_noul_verifier", call=call, parent=parent, attrs={"kind": d.kind, "noul": score})
                    jev_attrs = {"jev_noul": score}
                except Exception as exc:
                    tracer.add("model", "jev_noul_verifier", status="error", parent=parent, error=f"{type(exc).__name__}: {exc}"[:300])
            tracer.add("validator", d.kind, started=v0, parent=parent,
                       attrs={"accepted": report.accepted, "extractor": d.extractor_model, "payload": d.payload,
                              "evidence_ids": list(d.evidence_ids), "checks": [c.model_dump() for c in report.checks], **jev_attrs})
            if report.accepted:
                ledger.add_claim(to_claim(d, report))
            else:
                rejected.append({"draft": d.model_dump(), "report": report.model_dump()})

    def _finish(self, run_id: str, cand: CandidateState, t: float, night_id: str, tracer: Tracer, ledger: Ledger,
                outcome: Outcome, stop_reason: str, rejected: list[dict[str, Any]], tool_errors: dict[str, str],
                model_ids: dict[str, str], within_budget: bool, seed: int, n_tool: int) -> RunResult:
        tracer.add("plan", "stop", attrs={"outcome": outcome, "stop_reason": stop_reason})
        tin, tout, usd = tracer.totals()
        trace = Trace(run_id=run_id, oid=cand.oid, t_mjd=t, config_version=self.cfg.config_hash, mode="exploratory",
                      spans=tuple(tracer.spans), cost_usd=usd, model_ids=model_ids)
        frozen = ledger.freeze()
        hashed = {"ledger": frozen.model_dump(), "spans": [s.model_dump(exclude={"latency_ms"}) for s in tracer.spans],
                  "outcome": outcome, "stop_reason": stop_reason, "rejected": rejected}
        return RunResult(run_id, cand.oid, t, night_id, frozen, trace, outcome, stop_reason, rejected, tool_errors, within_budget,
                         sha256_hex(canonical_json(hashed)), seed,
                         {"tool_calls": n_tool, "input_tokens": tin, "output_tokens": tout, "usd": usd})


def _short(d: dict[str, Any]) -> dict[str, Any]:
    """Tool inputs for the trace, without the bulky candidate state (it is the Snapshot)."""
    return {k: ("<CandidateState>" if k == "candidate" else v) for k, v in d.items()}
