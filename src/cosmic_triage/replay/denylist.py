"""Denylist application: the type-level boundary between raw broker records and Snapshot(t).

``per_alert_allow`` (v1.1, Review-03) re-admits named per-alert fields for one source only: values an alert packet
carried at its own jd (e.g. Fink ``i:jdstarthist``) are time-honest, while the same names elsewhere — object-level
aggregates computed by a broker over everything it holds at query time — stay denied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cosmic_triage.settings import load_config


@dataclass(frozen=True)
class Denylist:
    version: str
    exact: frozenset[str]
    prefixes: tuple[str, ...]
    config_hash: str
    per_alert_allow: dict[str, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str = "configs/replay/denylist.yaml") -> Denylist:
        cfg, h = load_config(path)
        allow = {str(src): frozenset(keys) for src, keys in (cfg.get("per_alert_allow") or {}).items()}
        return cls(str(cfg["version"]), frozenset(cfg["exact"]), tuple(cfg.get("prefixes", [])), h, allow)

    def denied(self, key: str, source: str | None = None) -> bool:
        if source is not None and key in self.per_alert_allow.get(source, frozenset()):
            return False
        k = key.split(":", 1)[1] if key.startswith(("i:", "d:")) and key not in self.exact else key
        return key in self.exact or k in self.exact or key.startswith(self.prefixes) or k.startswith(self.prefixes)

    def scrub(self, record: dict[str, Any], source: str | None = None) -> dict[str, Any]:
        return {k: v for k, v in record.items() if not self.denied(k, source)}
