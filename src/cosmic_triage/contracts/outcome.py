from pydantic import Field

from cosmic_triage.contracts.base import ClassK, Contract, SimLevel
from cosmic_triage.contracts.value import ActionKind


class Outcome(Contract):
    """What replay revealed after executing an action (§3.3 step 5)."""

    oid: str
    night_id: str
    action: ActionKind
    realized_reward: float
    revealed_class: ClassK | None = None
    sim_level: SimLevel
    simulated: bool
    source: str = Field(description="e.g. 'bts_truth', 'confusion_reveal', 'ztf_record', 'posterior_draw'")
