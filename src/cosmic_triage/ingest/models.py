"""Paid-model clients: Claude (Anthropic SDK, structured output) and Jev (TypeSafe ``/v1/systemone``).

Both are cached by the full request (no secrets in it), so an offline replay of a recorded run never spends. Every
*live* call first passes ``SpendGuard.authorize`` (owner approval + $ cap) and then records its actual usage. The
transport is injectable so tests exercise parsing and the guard with explicit test doubles — those are never
presented as recorded API responses.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cosmic_triage import settings
from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.errors import CredentialMissing, ExternalAPIError
from cosmic_triage.ingest.http import HttpClient
from cosmic_triage.spend import SpendGuard

Transport = Callable[[dict[str, Any]], dict[str, Any]]

JEV_URL = "https://api.typesafe.ai/v1/systemone"
CLAUDE_HOW = "Create a key at console.anthropic.com and add ANTHROPIC_API_KEY=... to .env (spend also needs owner approval)."
JEV_HOW = "Create a key per docs.typesafe.ai quickstart and add TYPESAFE_API_KEY=... to .env (spend also needs owner approval)."


@dataclass(frozen=True)
class ModelCall:
    """One model call as the Investigator sees it. ``usd`` is what *this* call spent (0 on a cache hit)."""

    content: dict[str, Any]
    model_id: str
    input_tokens: int
    output_tokens: int
    usd: float
    cache_hit: bool
    request_hash: str
    response_hash: str


def _est_tokens(obj: Any) -> int:
    return len(settings.canonical_json(obj)) // 3 + 50  # conservative (~3 chars/token) for the pre-call estimate


class ClaudeClient:
    """Structured output via a single forced tool call; temperature 0; responses cached by request."""

    name = "anthropic"

    def __init__(self, cache: Cache, guard: SpendGuard, model: str, transport: Transport | None = None) -> None:
        self.cache = cache
        self.guard = guard
        self.model = model
        self.transport = transport or self._live

    def _live(self, request: dict[str, Any]) -> dict[str, Any]:
        key = settings.get_secret("ANTHROPIC_API_KEY")
        if not key:
            raise CredentialMissing("ANTHROPIC_API_KEY", CLAUDE_HOW)
        import anthropic

        msg = anthropic.Anthropic(api_key=key, max_retries=2).messages.create(**request)
        blocks = [b for b in msg.content if getattr(b, "type", "") == "tool_use"]
        if not blocks:
            raise ExternalAPIError(self.name, None, "no tool_use block in structured response")
        return {"model": msg.model, "content": dict(blocks[0].input),
                "usage": {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}}

    def structured(self, system: str, user: str, tool_name: str, schema: dict[str, Any], max_tokens: int,
                   run_id: str, purpose: str) -> ModelCall:
        request = {
            "model": self.model, "max_tokens": max_tokens, "temperature": 0, "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [{"name": tool_name, "description": f"Return {tool_name} as structured data.", "input_schema": schema}],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        return _call(self.cache, self.guard, self.name, "messages", self.model, request, max_tokens, self.transport,
                     run_id, purpose)


class JevClient:
    """TypeSafe Jev: many independent bounded questions per call (Noul / Choice / Score)."""

    name = "typesafe"

    def __init__(self, cache: Cache, guard: SpendGuard, model: str = "jev-latest", transport: Transport | None = None) -> None:
        self.cache = cache
        self.guard = guard
        self.model = model
        self.http = HttpClient(self.name, offline=cache.offline)
        self.transport = transport or self._live

    def _live(self, request: dict[str, Any]) -> dict[str, Any]:
        key = settings.get_secret("TYPESAFE_API_KEY")
        if not key:
            raise CredentialMissing("TYPESAFE_API_KEY", JEV_HOW)
        out: dict[str, Any] = self.http.request("POST", JEV_URL, json=request, headers={"Authorization": f"Bearer {key}"}).json()
        return {"model": out["model"], "content": out["answers"], "usage": out.get("usage", {})}

    def ask(self, state: Any, questions: dict[str, dict[str, Any]], run_id: str, purpose: str) -> ModelCall:
        request = {"state": state, "model": self.model, "questions": questions}
        return _call(self.cache, self.guard, self.name, "systemone", self.model, request, 0, self.transport, run_id, purpose)


def _call(cache: Cache, guard: SpendGuard, client: str, method: str, model: str, request: dict[str, Any],
          max_output_tokens: int, transport: Transport, run_id: str, purpose: str) -> ModelCall:
    req_hash = settings.sha256_hex(settings.canonical_json(request))
    spent: list[float] = []

    def fetch() -> dict[str, Any]:
        auth = guard.authorize(client, model, _est_tokens(request), max_output_tokens, run_id, purpose)
        raw = transport(request)
        usage = raw.get("usage") or {}
        spent.append(guard.record(auth, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)),
                                  str(raw.get("model", model)), run_id, purpose))
        return raw

    raw: dict[str, Any] = cache.get_or_fetch(client, method, request, fetch)
    usage = raw.get("usage") or {}
    return ModelCall(
        content=dict(raw["content"]), model_id=str(raw.get("model", model)),
        input_tokens=int(usage.get("input_tokens", 0)), output_tokens=int(usage.get("output_tokens", 0)),
        usd=spent[0] if spent else 0.0, cache_hit=not spent, request_hash=req_hash,
        response_hash=settings.sha256_hex(settings.canonical_json(raw["content"])),
    )
