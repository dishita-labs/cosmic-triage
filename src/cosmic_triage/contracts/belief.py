from pydantic import Field, model_validator

from cosmic_triage.contracts.base import ClassK, Contract


class Belief(Contract):
    """Posterior over coarse classes K for one candidate at t, with per-channel contributions (§3.2)."""

    oid: str
    t_mjd: float
    probs: dict[ClassK, float]
    channel_logp: dict[str, dict[ClassK, float]] = Field(default_factory=dict)
    entropy_nats: float
    phase_days: float | None = Field(default=None, description="Estimated days relative to peak")
    config_hash: str

    @model_validator(mode="after")
    def _normalised(self) -> "Belief":
        total = sum(self.probs.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"belief probabilities sum to {total}, not 1")
        if any(p < 0 for p in self.probs.values()):
            raise ValueError("negative probability")
        return self
