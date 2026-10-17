"""Denylist application: the type-level boundary between raw broker records and Snapshot(t)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cosmic_triage.settings import load_config


@dataclass(frozen=True)
class Denylist:
    version: str
    exact: frozenset[str]
    prefixes: tuple[str, ...]
    config_hash: str

    @classmethod
    def load(cls, path: str = "configs/replay/denylist.yaml") -> Denylist:
        cfg, h = load_config(path)
        return cls(str(cfg["version"]), frozenset(cfg["exact"]), tuple(cfg.get("prefixes", [])), h)

    def denied(self, key: str) -> bool:
        k = key.split(":", 1)[1] if key.startswith(("i:", "d:")) and key not in self.exact else key
        return key in self.exact or k in self.exact or key.startswith(self.prefixes) or k.startswith(self.prefixes)

    def scrub(self, record: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in record.items() if not self.denied(k)}
