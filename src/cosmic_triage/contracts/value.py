from typing import Literal

from pydantic import Field

from cosmic_triage.contracts.base import ClassK, Contract

ObjectiveId = Literal["O1", "O2", "O3", "O4"]
ActionKind = Literal["spectrum", "photometry", "wait"]


class Objective(Contract):
    id: ObjectiveId
    name: str
    description: str
    reward_table: str = Field(description="Path of the versioned reward-table YAML")


class RewardTable(Contract):
    """R(objective, class, phase_bin), hand-written, versioned, frozen before comparisons (§6.2)."""

    version: str
    objective: ObjectiveId
    phase_bins: tuple[str, ...]
    rewards: dict[ClassK, dict[str, float]]
    frozen_hash: str | None = None


class Action(Contract):
    kind: ActionKind
    oid: str
    instrument: str | None = None
    exposure_s: float | None = None
    expected_reward: float | None = None
    evsi: float | None = None
