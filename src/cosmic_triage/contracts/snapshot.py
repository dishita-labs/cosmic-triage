from pydantic import model_validator

from cosmic_triage.contracts.base import Contract
from cosmic_triage.contracts.candidate import CandidateState


class Snapshot(Contract):
    """The world as it was known at ``t_mjd`` (§3.3). The only input to belief/value/schedule/investigator."""

    t_mjd: float
    night_id: str
    candidates: tuple[CandidateState, ...]
    pool_config_hash: str
    denylist_version: str
    sources: dict[str, str]

    @model_validator(mode="after")
    def _nothing_after_t(self) -> "Snapshot":
        for c in self.candidates:
            if c.t_mjd != self.t_mjd:
                raise ValueError(f"candidate {c.oid} built for t={c.t_mjd}, snapshot t={self.t_mjd}")
            for p in c.photometry:
                if p.mjd > self.t_mjd:
                    raise ValueError(f"photometry at {p.mjd} > t={self.t_mjd} for {c.oid}")
            for r in c.fink_rows:
                if r.mjd > self.t_mjd:
                    raise ValueError(f"Fink row at {r.mjd} > t={self.t_mjd} for {c.oid}")
            if c.stamp_prior is not None and c.stamp_prior.first_alert_mjd > self.t_mjd:
                raise ValueError(f"stamp prior from the future for {c.oid}")
        return self
