"""ClaudeStructuredExtractor (Sonnet) → ClaimDrafts via a forced structured tool call (§4.1, §10.3 M2).

Behind ``flags.claude_extractor`` and the spend guard. Used for unstructured text and reconciliation; its drafts go
through the same validator chain as the RuleExtractor's. Evidence is presented as labelled cards built by code.
"""

from __future__ import annotations

from typing import Any

from cosmic_triage.contracts import ClaimDraft, Evidence
from cosmic_triage.ingest.models import ClaudeClient, ModelCall

SYSTEM = (
    "You extract typed claims about an astronomical transient from evidence cards. Use only the cards. "
    "Every claim must cite the card ids it relies on and copy values exactly as written in the cards; never compute, "
    "convert, or infer numbers or dates. If the cards support no claim, return an empty list."
)
CLAIM_KINDS = ["prior_classification", "host_redshift", "known_agn", "star_counterpart", "prior_flares", "nuclear",
               "analysis_result"]
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"claims": {"type": "array", "items": {
        "type": "object",
        "properties": {"kind": {"type": "string", "enum": CLAIM_KINDS}, "payload": {"type": "object"},
                       "evidence_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["kind", "payload", "evidence_ids"]}}},
    "required": ["claims"],
}


def cards(evidence: list[Evidence]) -> str:
    lines = []
    for e in evidence:
        fields = "; ".join(f"{k}={v}" for k, v in e.parsed.items() if not isinstance(v, dict | list))
        lines.append(f"[{e.id}] source={e.source} source_date_mjd={e.source_date} :: {fields}")
    return "\n".join(lines)


class ClaudeStructuredExtractor:
    name = "claude_structured"

    def __init__(self, client: ClaudeClient, max_tokens: int = 1200) -> None:
        self.client = client
        self.max_tokens = max_tokens
        self.calls: list[ModelCall] = []

    def draft_with_call(self, evidence: list[Evidence], run_id: str) -> tuple[list[ClaimDraft], ModelCall]:
        call = self.client.structured(SYSTEM, "Evidence cards:\n" + cards(evidence), "emit_claims", SCHEMA, self.max_tokens,
                                      run_id, "claim_extraction")
        drafts = []
        for c in call.content.get("claims", []):
            if isinstance(c, dict) and c.get("kind") in CLAIM_KINDS and isinstance(c.get("payload"), dict):
                drafts.append(ClaimDraft(kind=c["kind"], payload=c["payload"], evidence_ids=tuple(map(str, c.get("evidence_ids", []))),
                                         extractor_model=call.model_id))
        return drafts, call
