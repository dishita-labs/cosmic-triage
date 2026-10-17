from typing import Literal

from pydantic import Field

from cosmic_triage.contracts.base import Contract, JsonValue

EvidenceSource = Literal[
    "tns", "astronote", "atel", "gcn", "simbad", "ned", "sherlock", "gaia", "wise", "ps1",
    "alerce", "fink", "arxiv", "cutout", "tool",
]
ClaimKind = Literal[
    "prior_classification", "host_redshift", "known_agn", "star_counterpart",
    "prior_flares", "nuclear", "analysis_result",
]


class Evidence(Contract):
    id: str
    source: EvidenceSource
    source_date: float | None = Field(description="MJD of the record itself; None for static catalogs")
    retrieved_at_sim_time: float = Field(description="Simulated t of the run (MJD)")
    query: dict[str, JsonValue]
    raw_excerpt_hash: str
    parsed: dict[str, JsonValue]


class ValidationCheck(Contract):
    name: Literal["schema", "provenance", "date_le_t", "geometry", "type_specific", "support"]
    passed: bool
    detail: str = ""


class ValidationReport(Contract):
    accepted: bool
    checks: tuple[ValidationCheck, ...]
    support_score: float | None = None
    rejected_reasons: tuple[str, ...] = ()


class ClaimDraft(Contract):
    """An extractor's proposal; becomes a Claim only after validation (§4.4)."""

    kind: ClaimKind
    payload: dict[str, JsonValue]
    evidence_ids: tuple[str, ...]
    extractor_model: str


class Claim(Contract):
    kind: ClaimKind
    payload: dict[str, JsonValue]
    evidence_ids: tuple[str, ...]
    extractor_model: str
    validation: ValidationReport


class Compaction(Contract):
    """A summary of ledger entries that cites ids and never replaces the raw entries (§4.5)."""

    id: str
    created_at_sim_time: float
    summary: str
    cited_ids: tuple[str, ...]


class EvidenceLedger(Contract):
    oid: str
    entries: tuple[Evidence, ...] = ()
    claims: tuple[Claim, ...] = ()
    compactions: tuple[Compaction, ...] = ()
    version: str
