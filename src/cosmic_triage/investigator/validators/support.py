"""Claim-support verifiers (§4.4, §5 role 3): deterministic-only baseline and the exploratory Jev ``Noul``."""

from __future__ import annotations

import math
from typing import Any, Protocol

from cosmic_triage.contracts import ClaimDraft, Evidence
from cosmic_triage.ingest.models import JevClient, ModelCall


class SupportVerifier(Protocol):
    name: str

    def score(self, draft: ClaimDraft, evidence: list[Evidence], run_id: str) -> tuple[float, ModelCall | None]: ...


def _scalars(obj: Any, out: list[Any]) -> list[Any]:
    if isinstance(obj, dict):
        for v in obj.values():
            _scalars(v, out)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _scalars(v, out)
    elif obj is not None:
        out.append(obj)
    return out


def _supported(v: Any, pool: list[Any]) -> bool:
    if isinstance(v, bool):
        return v in pool
    if isinstance(v, int | float):
        return any(isinstance(p, int | float) and not isinstance(p, bool) and math.isclose(float(p), float(v), rel_tol=1e-6,
                                                                                            abs_tol=1e-6) for p in pool)
    return str(v) in {str(p) for p in pool}


# Payload fields the validator recomputes itself (geometry / derived), not copied from an excerpt.
DERIVED = {"sep_arcsec", "gap_days", "date_kind", "z_kind", "unit", "basis"}


class DeterministicVerifier:
    """1.0 iff every non-derived payload value appears verbatim (numbers within 1e-6) in the cited evidence, else 0.0."""

    name = "deterministic"

    def score(self, draft: ClaimDraft, evidence: list[Evidence], run_id: str) -> tuple[float, ModelCall | None]:
        pool: list[Any] = []
        for e in evidence:
            _scalars(e.parsed, pool)
        values = [v for k, v in draft.payload.items() if k not in DERIVED and v is not None]
        return (1.0 if all(_supported(v, pool) for v in values) else 0.0), None


class JevNoulVerifier:
    """Exploratory (flagged): Jev ``Noul`` over a claim sentence and labelled evidence fields. Never decides alone in
    M2 — the deterministic checks still gate acceptance; the score is logged for the M4 comparison."""

    name = "jev_noul"

    def __init__(self, jev: JevClient) -> None:
        self.jev = jev

    def score(self, draft: ClaimDraft, evidence: list[Evidence], run_id: str) -> tuple[float, ModelCall | None]:
        state = {"claim": {"kind": draft.kind, **draft.payload},
                 "evidence": [{"source": e.source, **{k: v for k, v in e.parsed.items() if not isinstance(v, list | dict)}}
                              for e in evidence]}
        call = self.jev.ask(state, {"supported": {
            "type": "noul", "instructions": "The evidence fields directly support every statement in the claim.",
            "criteria": {"true": "each claim field appears in or follows directly from an evidence field",
                         "false": "some claim field is absent from or contradicted by the evidence"}}}, run_id, "support_verifier")
        return float(call.content["supported"]["noul"]), call
