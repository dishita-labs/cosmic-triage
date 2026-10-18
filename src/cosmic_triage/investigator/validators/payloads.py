"""Typed payloads per claim kind (schema check of the validator chain, §4.4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from cosmic_triage.contracts.base import Contract
from cosmic_triage.contracts.evidence import ClaimKind


class PriorClassification(Contract):
    tns_class: str
    date_kind: Literal["report_date", "evidence_by"]
    date_mjd: float
    tns_name: str | None = None


class HostRedshift(Contract):
    z: float
    z_kind: Literal["spec", "photo"]
    host_id: str
    host_ra: float
    host_dec: float
    sep_arcsec: float
    catalog: str


class Counterpart(Contract):
    """known_agn / star_counterpart / nuclear: a catalogued source at a recomputed separation."""

    source_id: str
    source_type: str
    ra: float
    dec: float
    sep_arcsec: float
    catalog: str


class PriorFlares(Contract):
    """Earlier activity at the position, well before the current first known detection."""

    earlier_activity_mjd: float
    first_known_detection_mjd: float
    gap_days: float
    basis: Literal["alert_hist_start", "tns_discovery"]
    ref: str | None = None


class AnalysisResult(Contract):
    quantity: str
    value: float
    unit: str


PAYLOADS: dict[ClaimKind, type[BaseModel]] = {
    "prior_classification": PriorClassification,
    "host_redshift": HostRedshift,
    "known_agn": Counterpart,
    "star_counterpart": Counterpart,
    "nuclear": Counterpart,
    "prior_flares": PriorFlares,
    "analysis_result": AnalysisResult,
}
