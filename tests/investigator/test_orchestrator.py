"""Orchestrator: budgets, stop conditions, outcomes, determinism, failure handling (§4.2, §4.5, §13.5)."""

from __future__ import annotations

import dataclasses

from cosmic_triage.belief.stub import fink_stub_belief
from cosmic_triage.contracts import Objective
from cosmic_triage.investigator.config import InvestigatorConfig
from cosmic_triage.investigator.factory import Clients, build_orchestrator
from cosmic_triage.investigator.routers.gate import EntropyGate
from cosmic_triage.investigator.tools.base import ToolUpstreamError

from .helpers import DEC, RA, FakeLasair, FakeSimbad, FakeTNS, T, candidate, snapshot

OBJ = Objective(id="O1", name="Cosmology-grade SNe Ia", description="pre-peak SN Ia spectra", reward_table="-")
SHERLOCK_ROW = {"classification": "SN", "association_type": "SN", "catalogue_table_name": "SDSS/2MASS/PS1",
                "catalogue_object_id": 1237668332027641933, "catalogue_object_type": "galaxy", "raDeg": RA + 0.0017,
                "decDeg": DEC - 0.0034, "separationArcsec": 13.67, "z": 0.052, "photoZ": 0.041, "photoZErr": 0.012}


class FakeAlerce:
    def stamp(self, oid: str, candid: str, kind: str = "science", fmt: str = "png") -> bytes:
        return f"{oid}:{candid}:{kind}".encode()


class FailingSimbad(FakeSimbad):
    def __init__(self) -> None:
        super().__init__([])
        self.calls = 0

    def cone(self, *a, **k):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise ToolUpstreamError("simbad 503")


def orch(cfg: InvestigatorConfig | None = None, lasair: FakeLasair | None = None, simbad: FakeSimbad | None = None):  # type: ignore[no-untyped-def]
    clients = Clients(alerce=FakeAlerce(), lasair=lasair or FakeLasair(sherlock_rows=[SHERLOCK_ROW]), tns=FakeTNS(),  # type: ignore[arg-type]
                      simbad=simbad or FakeSimbad([]))  # type: ignore[arg-type]
    o = build_orchestrator(clients, cfg or dataclasses.replace(InvestigatorConfig.load(), slots={
        **InvestigatorConfig.load().slots, "gate": "always"}))
    o.backoff_base_s = 0.0
    return o


def go(o, c=None, seed=0):  # type: ignore[no-untyped-def]
    c = c or candidate()
    return o.run(c.oid, snapshot(c), OBJ, fink_stub_belief(c), seed=seed)


def test_end_to_end_claims_and_effect_inputs() -> None:
    r = go(orch())
    kinds = {c.kind for c in r.ledger.claims}
    assert r.outcome == "claims" and "host_redshift" in kinds and "analysis_result" in kinds
    assert r.within_budget and r.trace.cost_usd == 0.0


def test_every_accepted_claim_cites_only_evidence_le_t() -> None:
    r = go(orch())
    ev = {e.id: e for e in r.ledger.entries}
    for c in r.ledger.claims:
        for i in c.evidence_ids:
            assert ev[i].source_date is None or ev[i].source_date <= r.t_mjd


def test_resolved_stop_on_prior_classification() -> None:
    r = go(orch(), candidate(tns={T - 2.0: "SN Ia"}))
    assert r.stop_reason == "resolved:prior_classification"
    pc = [c for c in r.ledger.claims if c.kind == "prior_classification"]
    assert pc and pc[0].payload["date_kind"] == "evidence_by"


def test_tool_call_budget_is_hard() -> None:
    base = InvestigatorConfig.load()
    cfg = dataclasses.replace(base, slots={**base.slots, "gate": "always"},
                              budgets=dataclasses.replace(base.budgets, max_tool_calls=2))
    r = go(orch(cfg))
    assert r.stop_reason == "budget:tool_calls" and r.counters["tool_calls"] == 2 and r.within_budget


def test_upstream_errors_are_retried_then_recorded_and_the_run_still_terminates() -> None:
    sim = FailingSimbad()
    r = go(orch(simbad=sim))
    assert sim.calls == 1 + InvestigatorConfig.load().tools["max_retries"]
    assert "simbad_cone" in r.tool_errors and r.outcome in ("claims", "no_context_found")


def test_no_context_found_is_explicit() -> None:
    r = go(orch(lasair=FakeLasair()), candidate(ra=10.0, dec=-40.0))
    assert r.outcome == "no_context_found" and not r.ledger.claims


def test_entropy_gate_can_gate_out() -> None:
    base = InvestigatorConfig.load()
    o = orch(dataclasses.replace(base, slots={**base.slots, "gate": "entropy"}, entropy_threshold=99.0))
    assert isinstance(o.gate, EntropyGate)
    r = go(o)
    assert r.outcome == "gated_out" and r.counters["tool_calls"] == 0


def test_identical_inputs_give_identical_output_hashes() -> None:
    a, b = go(orch()), go(orch())
    assert a.output_hash == b.output_hash and a.run_id == b.run_id
    assert go(orch(), seed=1).run_id != a.run_id
