"""Builds an Orchestrator from configuration and ready-made clients (the investigator never touches the cache itself).
Paid slots are used only when their flag is on; they still need the owner's spend approval at call time."""

from __future__ import annotations

from dataclasses import dataclass

from cosmic_triage.ingest import AlerceClient, LasairClient, TNSClient
from cosmic_triage.ingest.catalogs import SimbadClient
from cosmic_triage.ingest.models import ClaudeClient, JevClient
from cosmic_triage.investigator.config import InvestigatorConfig
from cosmic_triage.investigator.extractors.claude import ClaudeStructuredExtractor
from cosmic_triage.investigator.orchestrator.loop import Orchestrator
from cosmic_triage.investigator.routers.gate import AlwaysGate, EntropyGate, Gate, JevNoulGate
from cosmic_triage.investigator.tools.base import ToolRegistry
from cosmic_triage.investigator.tools.calculator import OffsetAbsMagTool
from cosmic_triage.investigator.tools.cutouts import CutoutTool
from cosmic_triage.investigator.tools.history import AlertHistoryTool
from cosmic_triage.investigator.tools.reports import ReportLookupTool
from cosmic_triage.investigator.tools.sherlock import SherlockTool
from cosmic_triage.investigator.tools.simbad import SimbadConeTool
from cosmic_triage.investigator.validators.chain import Validator
from cosmic_triage.investigator.validators.support import DeterministicVerifier, JevNoulVerifier


@dataclass(frozen=True)
class Clients:
    alerce: AlerceClient
    lasair: LasairClient
    tns: TNSClient
    simbad: SimbadClient
    claude: ClaudeClient | None = None
    jev: JevClient | None = None


def build_registry(clients: Clients, cfg: InvestigatorConfig) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(AlertHistoryTool())
    reg.register(ReportLookupTool(clients.lasair, clients.tns, float(cfg.tools["report_radius_arcsec"])))
    reg.register(SherlockTool(clients.lasair))
    reg.register(SimbadConeTool(clients.simbad, float(cfg.tools["simbad_radius_arcsec"])))
    reg.register(CutoutTool(clients.alerce))
    reg.register(OffsetAbsMagTool())
    return reg


def build_orchestrator(clients: Clients, cfg: InvestigatorConfig | None = None, registry: ToolRegistry | None = None) -> Orchestrator:
    cfg = cfg or InvestigatorConfig.load()
    if cfg.mode != "exploratory":
        raise ValueError("M2 Investigator runs are exploratory only (§10.1)")
    gate: Gate = AlwaysGate() if cfg.slots["gate"] == "always" else EntropyGate(cfg.entropy_threshold)
    jev = clients.jev if (cfg.flags["jev_gate"] or cfg.flags["jev_verifier"]) else None
    if cfg.flags["jev_gate"] and jev is not None:
        gate = JevNoulGate(jev, gate)
    claude = None
    if cfg.flags["claude_extractor"] and "claude" in cfg.slots["extractor"] and clients.claude is not None:
        claude = ClaudeStructuredExtractor(clients.claude)
    return Orchestrator(cfg, registry or build_registry(clients, cfg), gate, Validator(cfg.validation, DeterministicVerifier()),
                        claude=claude, jev_verifier=JevNoulVerifier(jev) if (cfg.flags["jev_verifier"] and jev) else None)
