"""Spend cap enforced in code (§10.3 M2, §14.9): no paid call without owner approval; cap; cache hits are free."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from cosmic_triage.ingest import Cache
from cosmic_triage.ingest.models import ClaudeClient, JevClient
from cosmic_triage.investigator.extractors.claude import ClaudeStructuredExtractor
from cosmic_triage.spend import SpendCapExceeded, SpendGuard, SpendNotApproved, SpendPriceUnknown

from .helpers import T


def guard(tmp_path: Path, approved: bool, cap: float = 20.0) -> SpendGuard:
    cfg = yaml.safe_load(Path("configs/investigator/budget.yaml").read_text())
    cfg.update(total_cap_usd=cap, approved=approved, approval={"by": "test", "note": "unit test only"} if approved else None)
    p = tmp_path / "budget.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return SpendGuard(str(p), ledger_path=tmp_path / "spend.jsonl")


class Transport:
    """Explicit test double for a model transport — not a recorded API response."""

    def __init__(self, response: dict) -> None:  # type: ignore[type-arg]
        self.response, self.calls = response, 0

    def __call__(self, request: dict) -> dict:  # type: ignore[type-arg]
        self.calls += 1
        return self.response


def test_repository_budget_is_not_approved() -> None:
    g = SpendGuard()
    assert not g.approved and g.cap == 20.0


def test_unapproved_guard_refuses_before_any_transport_call(tmp_path: Path) -> None:
    tr = Transport({"model": "claude-sonnet-5-5", "content": {"claims": []}, "usage": {"input_tokens": 10, "output_tokens": 5}})
    client = ClaudeClient(Cache(root=tmp_path / "c", offline=False), guard(tmp_path, approved=False), "claude-sonnet-5-5", tr)
    with pytest.raises(SpendNotApproved):
        client.structured("s", "u", "emit_claims", {"type": "object"}, 100, "run", "test")
    assert tr.calls == 0
    log = [json.loads(x) for x in (tmp_path / "spend.jsonl").read_text().splitlines()]
    assert log[-1]["kind"] == "refused" and log[-1]["usd"] == 0.0


def test_cap_is_enforced_on_the_worst_case_estimate(tmp_path: Path) -> None:
    tr = Transport({"model": "claude-sonnet-5-5", "content": {"claims": []}, "usage": {"input_tokens": 10, "output_tokens": 5}})
    client = ClaudeClient(Cache(root=tmp_path / "c", offline=False), guard(tmp_path, approved=True, cap=0.001), "claude-sonnet-5-5", tr)
    with pytest.raises(SpendCapExceeded):
        client.structured("s", "u", "emit_claims", {"type": "object"}, 4000, "run", "test")
    assert tr.calls == 0


def test_unknown_model_price_is_refused(tmp_path: Path) -> None:
    g = guard(tmp_path, approved=True)
    with pytest.raises(SpendPriceUnknown):
        g.authorize("anthropic", "claude-unknown", 10, 10, "run", "test")


def test_approved_call_is_recorded_and_a_cache_hit_is_free(tmp_path: Path) -> None:
    g = guard(tmp_path, approved=True)
    resp = {"model": "claude-sonnet-5-5-20261001", "content": {"claims": [
        {"kind": "analysis_result", "payload": {"quantity": "q", "value": 1.0, "unit": "mag"}, "evidence_ids": ["ev-tool-x"]}]},
        "usage": {"input_tokens": 1000, "output_tokens": 200}}
    tr = Transport(resp)
    ext = ClaudeStructuredExtractor(ClaudeClient(Cache(root=tmp_path / "c", offline=False), g, "claude-sonnet-5-5", tr))
    drafts, call = ext.draft_with_call([], "run")
    assert tr.calls == 1 and not call.cache_hit and call.usd == pytest.approx((1000 * 3 + 200 * 15) / 1e6)
    assert drafts[0].extractor_model == "claude-sonnet-5-5-20261001"   # resolved id, not the alias
    assert g.spent() == pytest.approx(call.usd)
    drafts2, call2 = ext.draft_with_call([], "run")
    assert drafts2 == drafts
    assert tr.calls == 1 and call2.cache_hit and call2.usd == 0.0 and g.spent() == pytest.approx(call.usd)


def test_jev_client_parses_noul_and_charges_input_only(tmp_path: Path) -> None:
    g = guard(tmp_path, approved=True)
    tr = Transport({"model": "jev-1.14.0", "content": {"supported": {"type": "noul", "noul": 0.93}},
                    "usage": {"input_tokens": 500, "output_tokens": 20}})
    call = JevClient(Cache(root=tmp_path / "c", offline=False), g, "jev-latest", tr).ask({"claim": "x"}, {
        "supported": {"type": "noul", "instructions": "?"}}, "run", "test")
    assert call.content["supported"]["noul"] == 0.93 and call.usd == pytest.approx(500 * 0.042 / 1e6)


def test_offline_cache_miss_never_reaches_the_guard(tmp_path: Path) -> None:
    from cosmic_triage.ingest.errors import OfflineCacheMiss

    tr = Transport({})
    client = JevClient(Cache(root=tmp_path / "c", offline=True), guard(tmp_path, approved=True), "jev-latest", tr)
    with pytest.raises(OfflineCacheMiss):
        client.ask({"t": T}, {"q": {"type": "noul", "instructions": "?"}}, "run", "test")
    assert tr.calls == 0 and not (tmp_path / "spend.jsonl").exists()
