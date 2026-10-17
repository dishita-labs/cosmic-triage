"""Replay clock: builds Snapshot(t) (ARCHITECTURE §3.3 step 1, §13.3).

Everything that reaches a Snapshot is (a) denylist-scrubbed and (b) filtered to ``mjd <= t``; every aggregate
(detection counts, brightest/latest magnitude, first detection, position) is recomputed from those records.
"""

from __future__ import annotations

import math
from typing import Any

from astropy.time import Time

from cosmic_triage.contracts import CandidateContext, CandidateState, FinkAlertRow, PhotometryPoint, Snapshot
from cosmic_triage.replay.denylist import Denylist
from cosmic_triage.replay.pool import ForwardPool, RawCandidate, _f, _positive, galactic_b

BANDS = {1: "g", 2: "r", 3: "i"}
SOURCES = {"alerce": "api.alerce.online/ztf/v1", "fink": "api.ztf.fink-portal.org/api/v1", "lasair": "lasair-ztf (superset)"}


def night_id_for_t(t_mjd: float, decision_time_utc_hour: float = 20.0) -> str:
    # Half a second of slack so a t written with truncated decimals still maps to its own night.
    local_midnight = t_mjd - decision_time_utc_hour / 24.0 + 0.5 / 86400.0
    return str(Time(local_midnight, format="mjd", scale="utc").to_value("iso", subfmt="date"))


def _str(x: Any) -> str | None:
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    return str(x)


def build_candidate(raw: RawCandidate, t: float) -> CandidateState:
    phot: list[PhotometryPoint] = []
    for d in raw.dets_le(t):
        mag = _f(d.get("magpsf"))
        band = BANDS.get(int(d.get("fid", 0) or 0))
        if mag is None or band is None:
            continue
        phot.append(PhotometryPoint(
            mjd=float(d["mjd"]), band=band, is_detection=True, mag=mag, mag_err=_f(d.get("sigmapsf")),
            drb=_f(d.get("drb")), isdiffpos=_positive(d.get("isdiffpos")), candid=_str(d.get("candid")), source="alerce",
        ))
    n_nd = 0
    for n in raw.non_detections:
        if n["mjd"] > t:
            continue
        band = BANDS.get(int(n.get("fid", 0) or 0))
        lim = _f(n.get("diffmaglim"))
        if band is None or lim is None:
            continue
        n_nd += 1
        phot.append(PhotometryPoint(mjd=float(n["mjd"]), band=band, is_detection=False, limiting_mag=lim, source="alerce"))
    phot.sort(key=lambda p: (p.mjd, p.band, p.is_detection))
    dets = [p for p in phot if p.is_detection]
    if not dets:
        raise ValueError(f"{raw.oid}: no detections <= t")
    pos_dets = [p for p in dets if p.isdiffpos is not False] or dets
    fink = tuple(
        FinkAlertRow(
            mjd=float(r["mjd"]), candid=_str(r.get("i:candid")),
            rf_snia_vs_nonia=_f(r.get("d:rf_snia_vs_nonia")), snn_snia_vs_nonia=_f(r.get("d:snn_snia_vs_nonia")),
            snn_sn_vs_all=_f(r.get("d:snn_sn_vs_all")), cdsxmatch=_str(r.get("d:cdsxmatch")),
            tns_alert_time=_str(r.get("d:tns")),
        )
        for r in raw.fink_rows if r["mjd"] <= t
    )
    pos = raw.position_le(t)
    assert pos is not None
    ctx = raw.static_context(t)
    latest = max(pos_dets, key=lambda p: p.mjd)
    return CandidateState(
        oid=raw.oid, t_mjd=t,
        context=CandidateContext(ra=pos[0], dec=pos[1], gal_b=galactic_b(*pos), **ctx),
        photometry=tuple(phot), fink_rows=fink, stamp_prior=None,
        first_detection_mjd=min(p.mjd for p in dets), last_detection_mjd=max(p.mjd for p in dets),
        n_detections=len(dets), n_nondetections=n_nd,
        brightest_mag=min(p.mag for p in pos_dets if p.mag is not None),
        latest_mag=float(latest.mag) if latest.mag is not None else math.inf, latest_band=latest.band,
    )


class Clock:
    def __init__(self, deny: Denylist | None = None, decision_time_utc_hour: float = 20.0) -> None:
        self.deny = deny or Denylist.load()
        self.decision_time_utc_hour = decision_time_utc_hour

    def snapshot(self, t_mjd: float, pool: ForwardPool) -> Snapshot:
        oids = pool.candidates(t_mjd)
        cands = tuple(build_candidate(pool.raw(o), t_mjd) for o in oids)
        return Snapshot(
            t_mjd=t_mjd, night_id=night_id_for_t(t_mjd, self.decision_time_utc_hour), candidates=cands,
            pool_config_hash=pool.cfg.config_hash, denylist_version=f"{self.deny.version}:{self.deny.config_hash}",
            sources=SOURCES,
        )
