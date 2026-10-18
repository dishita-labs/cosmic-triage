"""Investigator configuration (configs/investigator/investigator.yaml); its content hash is the run's config_version."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cosmic_triage.investigator.validators.chain import ValidationConfig
from cosmic_triage.settings import load_config


@dataclass(frozen=True)
class Budgets:
    max_tool_calls: int
    max_model_calls: int
    max_tokens: int
    max_usd: float
    max_wall_s: float


@dataclass(frozen=True)
class InvestigatorConfig:
    version: str
    config_hash: str
    mode: str
    slots: dict[str, str]
    flags: dict[str, bool]
    models: dict[str, str]
    entropy_threshold: float
    order: tuple[str, ...]
    budgets: Budgets
    patience: int
    stop_when_resolved: bool
    tools: dict[str, Any]
    validation: ValidationConfig

    @classmethod
    def load(cls, path: str = "configs/investigator/investigator.yaml") -> InvestigatorConfig:
        c, h = load_config(path)
        v = c["validation"]
        return cls(
            version=str(c["version"]), config_hash=h, mode=str(c["mode"]), slots=dict(c["slots"]),
            flags={k: bool(x) for k, x in c["flags"].items()}, models=dict(c["models"]),
            entropy_threshold=float(c["gate"]["entropy_threshold_nats"]), order=tuple(c["planner"]["order"]),
            budgets=Budgets(max_tool_calls=int(c["budgets"]["max_tool_calls"]), max_model_calls=int(c["budgets"]["max_model_calls"]),
                            max_tokens=int(c["budgets"]["max_tokens"]), max_usd=float(c["budgets"]["max_usd"]),
                            max_wall_s=float(c["budgets"]["max_wall_s"])),
            patience=int(c["stop"]["no_new_evidence_patience"]), stop_when_resolved=bool(c["stop"]["stop_when_resolved"]),
            tools=dict(c["tools"]),
            validation=ValidationConfig(support_threshold=float(v["support_threshold"]),
                                        geometry_tolerance_arcsec=float(v["geometry_tolerance_arcsec"]),
                                        z_min=float(v["z_range"][0]), z_max=float(v["z_range"][1]),
                                        radius={str(k): float(x) for k, x in v["association_radius_arcsec"].items()}),
        )
