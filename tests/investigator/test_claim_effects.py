from __future__ import annotations

import pytest

from cosmic_triage.contracts import Claim, ValidationReport
from cosmic_triage.value.claim_effects import ClaimEffects


def claim(kind: str, accepted: bool = True) -> Claim:
    return Claim(kind=kind, payload={}, evidence_ids=("ev-1",), extractor_model="rule-v1",  # type: ignore[arg-type]
                 validation=ValidationReport(accepted=accepted, checks=()))


def test_prior_classification_zeroes_spectrum_reward_and_others_are_deferred() -> None:
    f, log = ClaimEffects().apply((claim("host_redshift"), claim("prior_classification")))
    assert f == 0.0 and [e.status for e in log] == ["deferred", "applied"]


def test_unvalidated_claim_cannot_reach_effects() -> None:
    with pytest.raises(ValueError):
        ClaimEffects().apply((claim("prior_classification", accepted=False),))
