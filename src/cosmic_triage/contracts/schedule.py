from typing import Literal

from cosmic_triage.contracts.base import Contract
from cosmic_triage.contracts.value import ActionKind


class ScheduledObservation(Contract):
    oid: str
    action: ActionKind
    start_mjd: float
    end_mjd: float
    exposure_s: float
    overhead_s: float


class Schedule(Contract):
    night_id: str
    facility_id: str
    budget: int
    items: tuple[ScheduledObservation, ...]
    solver: Literal["cpsat", "greedy", "none"]
    solver_status: str
    objective_value: float | None = None
    config_hash: str
