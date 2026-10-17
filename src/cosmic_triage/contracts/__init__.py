"""Typed, versioned contracts (§3, §4.3, §13.3). Additive optional fields are fine; semantic changes go to Fable (§14)."""

from cosmic_triage.contracts.base import CLASSES_K, ClassK, Contract, Label, RunMode, SimLevel
from cosmic_triage.contracts.belief import Belief
from cosmic_triage.contracts.candidate import CandidateContext, CandidateState, FinkAlertRow, StampPrior
from cosmic_triage.contracts.evidence import (
    Claim,
    ClaimDraft,
    Compaction,
    Evidence,
    EvidenceLedger,
    ValidationCheck,
    ValidationReport,
)
from cosmic_triage.contracts.outcome import Outcome
from cosmic_triage.contracts.photometry import PhotometryPoint
from cosmic_triage.contracts.run import RunConfig, RunManifest
from cosmic_triage.contracts.schedule import Schedule, ScheduledObservation
from cosmic_triage.contracts.snapshot import Snapshot
from cosmic_triage.contracts.theater import (
    FacilityState,
    FrameCandidate,
    MoonState,
    NightFrame,
    TheaterEvent,
    TheaterNight,
)
from cosmic_triage.contracts.trace import ActionValue, DecisionTrace, Span, Trace
from cosmic_triage.contracts.value import Action, Objective, RewardTable

CONTRACTS_VERSION = "1.0.0"

ALL_CONTRACTS: tuple[type[Contract], ...] = (
    PhotometryPoint, CandidateContext, FinkAlertRow, StampPrior, CandidateState, Snapshot, Belief,
    Objective, RewardTable, Action, ScheduledObservation, Schedule, Outcome, Evidence, ValidationCheck,
    ValidationReport, ClaimDraft, Claim, Compaction, EvidenceLedger, Span, Trace, ActionValue,
    DecisionTrace, RunConfig, RunManifest, MoonState, FrameCandidate, FacilityState, TheaterEvent,
    NightFrame, TheaterNight,
)

__all__ = [
    "ALL_CONTRACTS", "CLASSES_K", "CONTRACTS_VERSION", "Action", "ActionValue", "Belief",
    "CandidateContext", "CandidateState", "Claim", "ClaimDraft", "ClassK", "Compaction", "Contract",
    "DecisionTrace", "Evidence", "EvidenceLedger", "FacilityState", "FinkAlertRow", "FrameCandidate",
    "Label", "MoonState", "NightFrame", "Objective", "Outcome", "PhotometryPoint", "RewardTable",
    "RunConfig", "RunManifest", "RunMode", "Schedule", "ScheduledObservation", "SimLevel", "Snapshot",
    "Span", "StampPrior", "TheaterEvent", "TheaterNight", "Trace", "ValidationCheck",
    "ValidationReport",
]
