"""Investigation gate slot (§4.2, §5 role 1): AlwaysGate, EntropyGate (baseline), JevNoulGate (exploratory, flagged)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cosmic_triage.contracts import Belief, Objective
from cosmic_triage.ingest.models import JevClient, ModelCall


@dataclass(frozen=True)
class GateDecision:
    investigate: bool
    reason: str
    score: float | None = None
    call: ModelCall | None = None


class Gate(Protocol):
    name: str

    def decide(self, belief: Belief, objective: Objective, run_id: str) -> GateDecision: ...


class AlwaysGate:
    name = "always"

    def decide(self, belief: Belief, objective: Objective, run_id: str) -> GateDecision:
        return GateDecision(True, "always")


class EntropyGate:
    name = "entropy"

    def __init__(self, threshold_nats: float) -> None:
        self.threshold = threshold_nats

    def decide(self, belief: Belief, objective: Objective, run_id: str) -> GateDecision:
        go = belief.entropy_nats >= self.threshold
        return GateDecision(go, f"entropy {belief.entropy_nats:.3f} {'>=' if go else '<'} {self.threshold} nats", belief.entropy_nats)


class JevNoulGate:
    """Exploratory: logged alongside the entropy decision; in M2 it never overrides the baseline (not yet gating)."""

    name = "jev_noul"

    def __init__(self, jev: JevClient, baseline: Gate) -> None:
        self.jev = jev
        self.baseline = baseline

    def decide(self, belief: Belief, objective: Objective, run_id: str) -> GateDecision:
        base = self.baseline.decide(belief, objective, run_id)
        top = sorted(belief.probs.items(), key=lambda kv: -kv[1])[:3]
        state = {"objective": objective.name, "objective_description": objective.description,
                 "belief_top_classes": [{"class": k, "probability": round(v, 2)} for k, v in top]}
        call = self.jev.ask(state, {"worth": {"type": "noul", "instructions":
                                              "Investigating this candidate's context is worth it given the objective and belief."}},
                            run_id, "gate")
        score = float(call.content["worth"]["noul"])
        return GateDecision(base.investigate, f"{base.reason}; jev_noul={score:.3f} (logged, not gating in M2)", score, call)
