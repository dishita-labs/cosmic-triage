"""Tool contract, typed errors and the registry (ARCHITECTURE §4.2, §13.3).

Every tool takes a typed input, returns a typed output plus ``Evidence`` records, and applies its **as-of filter at the
tool layer**: nothing with ``source_date > t`` (and no field that only became true after t) may leave a tool. The
registry adds a second, source-agnostic as-of check so one tool's bug cannot leak into the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from cosmic_triage.contracts import CandidateState, Evidence
from cosmic_triage.contracts.evidence import EvidenceSource
from cosmic_triage.settings import canonical_json, sha256_hex


class ToolError(Exception):
    """Base class. ``retryable`` errors are retried with backoff by the orchestrator; others fail the call once."""

    retryable = False


class ToolInputError(ToolError):
    pass


class ToolUnavailable(ToolError):
    """Credential missing, offline cache miss, or circuit open: the tool cannot run in this configuration."""


class ToolUpstreamError(ToolError):
    retryable = True


class ToolAsOfViolation(ToolError):
    """A tool tried to emit evidence dated after t. Always a bug; the evidence is dropped and the span marked."""


@dataclass(frozen=True)
class ToolContext:
    t_mjd: float
    candidate: CandidateState
    run_id: str


@dataclass(frozen=True)
class ToolResult:
    output: BaseModel
    evidence: tuple[Evidence, ...]
    cache_hit: bool | None = None
    filtered_post_t: int = 0


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    as_of_aware: bool


class LedgerView(Protocol):
    def entries(self) -> tuple[Evidence, ...]: ...


class Tool(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def Input(self) -> type[BaseModel]: ...
    @property
    def Output(self) -> type[BaseModel]: ...
    @property
    def as_of_aware(self) -> bool: ...

    def build_input(self, ctx: ToolContext, ledger: LedgerView) -> BaseModel | None:
        """The input for this candidate given the ledger so far, or None when the tool does not apply."""
        ...

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult: ...


def make_evidence(source: EvidenceSource, source_date: float | None, t_mjd: float, query: dict[str, Any],
                  raw: Any, parsed: dict[str, Any]) -> Evidence:
    """Evidence with a deterministic id over (source, query, parsed); the raw record is kept only as a hash."""
    ident = sha256_hex(canonical_json({"source": source, "query": query, "parsed": parsed}))[:12]
    return Evidence(id=f"ev-{source}-{ident}", source=source, source_date=source_date, retrieved_at_sim_time=t_mjd,
                    query=query, raw_excerpt_hash=sha256_hex(canonical_json(raw)), parsed=parsed)


def check_as_of(evidence: tuple[Evidence, ...], t_mjd: float) -> None:
    bad = [e.id for e in evidence if (e.source_date is not None and e.source_date > t_mjd) or e.retrieved_at_sim_time != t_mjd]
    if bad:
        raise ToolAsOfViolation(f"evidence dated after t={t_mjd} or retrieved at another t: {bad}")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool {name!r}")
        return self._tools[name]

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def describe(self) -> list[ToolSpec]:
        return [ToolSpec(t.name, t.description, t.Input.model_json_schema(), t.as_of_aware) for t in self._tools.values()]

    def run(self, name: str, inp: BaseModel, t_mjd: float) -> ToolResult:
        tool = self.get(name)
        if not isinstance(inp, tool.Input):
            raise ToolInputError(f"{name}: expected {tool.Input.__name__}, got {type(inp).__name__}")
        res = tool.run(inp, t_mjd)
        if not isinstance(res.output, tool.Output):
            raise ToolError(f"{name}: returned {type(res.output).__name__}, expected {tool.Output.__name__}")
        check_as_of(res.evidence, t_mjd)
        return res
