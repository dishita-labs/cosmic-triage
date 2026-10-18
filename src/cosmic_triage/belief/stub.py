"""Stub belief from alert-time Fink scores (ARCHITECTURE §10.4 vertical slice). **Not** the M3 belief: uncalibrated,
used only to drive the exploratory gate until the calibrated pool exists. Snapshot-only input."""

from __future__ import annotations

import math

from cosmic_triage.contracts import Belief, CandidateState
from cosmic_triage.contracts.base import CLASSES_K, ClassK

STUB_ID = "stub-fink-v1"
EPS = 0.01


def fink_stub_belief(c: CandidateState) -> Belief:
    rows = sorted(c.fink_rows, key=lambda r: r.mjd)
    last = rows[-1] if rows else None
    p_sn = last.snn_sn_vs_all if last and last.snn_sn_vs_all is not None else 0.5
    p_ia_given_sn = last.snn_snia_vs_nonia if last and last.snn_snia_vs_nonia is not None else 0.5
    raw: dict[ClassK, float] = {
        "Ia": p_sn * p_ia_given_sn, "II": p_sn * (1 - p_ia_given_sn) * 0.6, "Ibc": p_sn * (1 - p_ia_given_sn) * 0.3,
        "other_luminous": p_sn * (1 - p_ia_given_sn) * 0.1, "contaminant": 1 - p_sn,
    }
    tot = sum(max(v, EPS) for v in raw.values())
    probs: dict[ClassK, float] = {k: max(raw[k], EPS) / tot for k in CLASSES_K}
    probs["contaminant"] = 1.0 - sum(v for k, v in probs.items() if k != "contaminant")
    ent = -sum(p * math.log(p) for p in probs.values() if p > 0)
    return Belief(oid=c.oid, t_mjd=c.t_mjd, probs=probs, entropy_nats=ent, config_hash=STUB_ID)
