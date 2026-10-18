"""Planner slot (§4.2): FixedOrderPlanner — each tool at most once, in configured order."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    name: str


@dataclass(frozen=True)
class Stop:
    reason: str


class FixedOrderPlanner:
    name = "fixed"

    def __init__(self, order: tuple[str, ...]) -> None:
        self.order = order

    def next_tool(self, attempted: set[str], available: tuple[str, ...]) -> ToolCall | Stop:
        for n in self.order:
            if n in available and n not in attempted:
                return ToolCall(n)
        return Stop("plan_exhausted")
