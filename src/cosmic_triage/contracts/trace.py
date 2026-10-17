from typing import Literal

from pydantic import Field

from cosmic_triage.contracts.base import Contract, JsonValue, RunMode
from cosmic_triage.contracts.value import ActionKind

SpanKind = Literal["tool", "model", "validator", "solver", "gate", "plan", "extract", "replay"]


class Span(Contract):
    span_id: str
    parent_id: str | None = None
    kind: SpanKind
    name: str
    status: Literal["ok", "error", "skipped"] = "ok"
    latency_ms: float | None = Field(default=None, description="Wall-clock; excluded from output hashes")
    model_id: str | None = Field(default=None, description="Resolved model id, never an alias")
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    cache_hit: bool | None = None
    prompt_hash: str | None = None
    response_hash: str | None = None
    error: str | None = None
    attrs: dict[str, JsonValue] = Field(default_factory=dict)


class Trace(Contract):
    """One per Investigator run; read by the console (§4.3)."""

    run_id: str
    oid: str
    t_mjd: float
    config_version: str
    mode: RunMode
    spans: tuple[Span, ...]
    cost_usd: float
    model_ids: dict[str, str]


class ActionValue(Contract):
    kind: ActionKind
    value: float
    components: dict[str, float] = Field(default_factory=dict)


class DecisionTrace(Contract):
    """Per candidate per night: what was considered, what was chosen, and why not the rest."""

    run_id: str
    night_id: str
    oid: str
    t_mjd: float
    belief_top: str | None = None
    considered: tuple[ActionValue, ...]
    chosen: ActionKind | None
    reason: str
    why_not: dict[str, str] = Field(default_factory=dict)
