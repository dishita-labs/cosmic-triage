"""Span recording (§4.5 observability). Span ids are sequential, so identical runs yield identical traces apart from
wall-clock latency, which is excluded from output hashes."""

from __future__ import annotations

import time
from typing import Any, Literal

from cosmic_triage.contracts import Span
from cosmic_triage.contracts.trace import SpanKind
from cosmic_triage.ingest.models import ModelCall


class Tracer:
    def __init__(self) -> None:
        self.spans: list[Span] = []
        self._n = 0

    def next_id(self) -> str:
        self._n += 1
        return f"s{self._n:03d}"

    def add(self, kind: SpanKind, name: str, *, started: float | None = None, status: Literal["ok", "error", "skipped"] = "ok", parent: str | None = None,
            call: ModelCall | None = None, cache_hit: bool | None = None, error: str | None = None,
            attrs: dict[str, Any] | None = None) -> Span:
        span = Span(
            span_id=self.next_id(), parent_id=parent, kind=kind, name=name, status=status,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 1) if started is not None else None,
            model_id=call.model_id if call else None, input_tokens=call.input_tokens if call else 0,
            output_tokens=call.output_tokens if call else 0, usd=call.usd if call else 0.0,
            cache_hit=call.cache_hit if call else cache_hit, prompt_hash=call.request_hash if call else None,
            response_hash=call.response_hash if call else None, error=error, attrs=attrs or {},
        )
        self.spans.append(span)
        return span

    def totals(self) -> tuple[int, int, float]:
        return (sum(s.input_tokens for s in self.spans), sum(s.output_tokens for s in self.spans),
                round(sum(s.usd for s in self.spans), 6))
