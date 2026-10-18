"""Per-run evidence ledger builder over the immutable ``EvidenceLedger`` contract (ARCHITECTURE §4.3, §4.5)."""

from __future__ import annotations

from cosmic_triage.contracts import Claim, ClaimDraft, Evidence, EvidenceLedger, ValidationReport

LEDGER_VERSION = "1.0"


class Ledger:
    def __init__(self, oid: str) -> None:
        self.oid = oid
        self._entries: dict[str, Evidence] = {}
        self._claims: list[Claim] = []
        self.rejected: list[tuple[ClaimDraft, ValidationReport]] = []

    def add(self, ev: Evidence) -> bool:
        """Add evidence; returns False if an identical record (same id) is already present (idempotent)."""
        if ev.id in self._entries:
            return False
        self._entries[ev.id] = ev
        return True

    def get(self, evidence_id: str) -> Evidence | None:
        return self._entries.get(evidence_id)

    def entries(self) -> tuple[Evidence, ...]:
        return tuple(self._entries.values())

    def claims(self) -> tuple[Claim, ...]:
        return tuple(self._claims)

    def has_claim(self, draft: ClaimDraft) -> bool:
        return any(c.kind == draft.kind and c.payload == draft.payload and c.evidence_ids == draft.evidence_ids for c in self._claims)

    def add_claim(self, claim: Claim) -> None:
        if not claim.validation.accepted:
            raise ValueError("only validated claims enter the ledger")
        self._claims.append(claim)

    def freeze(self) -> EvidenceLedger:
        return EvidenceLedger(oid=self.oid, entries=self.entries(), claims=self.claims(), version=LEDGER_VERSION)
