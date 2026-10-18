"""ClaimEffects (§13.3): validated Claims → code-owned effects. The only path by which Investigator output can touch a
reward (§1.4). M2 implements the spectrum-reward factor; belief effects arrive with the M3 pool."""

from __future__ import annotations

from dataclasses import dataclass

from cosmic_triage.contracts import Claim
from cosmic_triage.settings import load_config


@dataclass(frozen=True)
class Effect:
    claim_kind: str
    target: str
    factor: float | None
    status: str  # "applied" | "deferred"
    evidence_ids: tuple[str, ...]


class ClaimEffects:
    def __init__(self, path: str = "configs/objectives/claim_effects.yaml") -> None:
        cfg, self.config_hash = load_config(path)
        self.factors = {str(k): float(v) for k, v in cfg["spectrum_reward_factor"].items()}
        self.deferred = set(cfg["deferred_to_m3"])

    def apply(self, claims: tuple[Claim, ...]) -> tuple[float, list[Effect]]:
        """Returns the multiplicative factor on the terminal (spectrum) reward and the effect log."""
        factor, log = 1.0, []
        for c in claims:
            if not c.validation.accepted:
                raise ValueError("unvalidated claim reached ClaimEffects")
            if c.kind in self.factors:
                factor *= self.factors[c.kind]
                log.append(Effect(c.kind, "spectrum_reward", self.factors[c.kind], "applied", c.evidence_ids))
            elif c.kind in self.deferred:
                log.append(Effect(c.kind, "belief/reward (M3)", None, "deferred", c.evidence_ids))
        return factor, log
