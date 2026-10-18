"""Truth labels from the BTS catalog snapshot (ARCHITECTURE §6.4). Replay-only: reads truth and the future.

- BTS-saved & classified       -> label "class" (coarse class K via configs/replay/class_map.yaml)
- BTS-saved & unclassified     -> label "unknown" (reported under three treatments downstream)
- never-saved & filter-passing & bright -> label "contaminant" (BTS II TNS audit: ~0.6% missed)
- never-saved & not bright     -> no label (outside the scored regime)
"Bright" = peak <= scored_peak_mag (18.5): the BTS peak for saved objects, else the object's brightest *qualifying*
detection over its full history — drb >= min_drb and positive subtraction (Review-03 §6.4 (a); replay may read the
future; nothing here reaches a Snapshot). Contaminant labels are provisional until the labels audit
(runs/reports/labels_audit.md) is complete.
"""

from __future__ import annotations

from dataclasses import dataclass

from cosmic_triage.contracts import ClassK, Label
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.replay.pool import RawCandidate, _f, _positive
from cosmic_triage.settings import load_config


@dataclass(frozen=True)
class TruthLabel:
    oid: str
    label: Label | None
    coarse_class: ClassK | None
    bts_type: str | None
    peak_mag: float | None
    bright: bool
    saved: bool


class ClassMap:
    def __init__(self, path: str = "configs/replay/class_map.yaml") -> None:
        cfg, self.config_hash = load_config(path)
        self.version = str(cfg["version"])
        self._map: dict[str, ClassK] = {}
        for k in ("Ia", "II", "Ibc", "other_luminous", "contaminant"):
            for t in cfg.get(k, []):
                self._map[str(t).strip()] = k

    def coarse(self, bts_type: str) -> ClassK | None:
        return self._map.get(bts_type.strip())


def full_history_peak(raw: RawCandidate, min_drb: float = 0.5) -> float | None:
    """Brightest qualifying detection over the full history: drb >= min_drb and positive subtraction."""
    mags = [m for d in raw.detections
            if _positive(d.get("isdiffpos")) is True and (drb := _f(d.get("drb"))) is not None and drb >= min_drb
            and (m := _f(d.get("magpsf"))) is not None]
    return min(mags) if mags else None


def label_candidate(
    oid: str, raw: RawCandidate | None, bts: BTSCatalog, cmap: ClassMap, scored_peak_mag: float, min_drb: float = 0.5
) -> TruthLabel:
    row = bts.row(oid)
    if row is not None:
        peak = _f(row.get("peakmag_f"))
        bright = peak is not None and peak <= scored_peak_mag
        t = str(row["type"]).strip()
        lab = bts.label(oid, scored_regime=bright)
        return TruthLabel(oid, lab, cmap.coarse(t) if lab == "class" else None, t if lab == "class" else None, peak, bright, True)
    peak = full_history_peak(raw, min_drb) if raw is not None else None
    bright = peak is not None and peak <= scored_peak_mag
    if bright:
        return TruthLabel(oid, bts.label(oid, scored_regime=True), "contaminant", None, peak, True, False)
    return TruthLabel(oid, None, None, None, peak, False, False)
