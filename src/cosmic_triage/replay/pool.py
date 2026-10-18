"""Forward candidate pool with the time-honest pre-filter (ARCHITECTURE §3.3 step 1, §6.4).

Retrieval is two-stage:

1. **Superset (cheap, necessary conditions only).** ALeRCE objects first alerted in the window with final
   ``ndet >= 2`` and all-time brightest magnitude <= 19 (both monotone over an object's history, so necessary at
   any t), outside |b| < 6.5 deg and not star-like in *every* PS1 crossmatch row (static context). Any object
   that passes the true filter at some t in the window satisfies all of these, so the superset never drops a true
   pool member. Final aggregates are used only to *exclude* objects that can never qualify; they never enter a
   Snapshot. (Lasair's object aggregates were rejected for this: they cover a rolling recent window, not the full
   history, so they are not monotone — see runs/reports/M1.md.)
2. **Time-honest filter at t** (`evaluate`), computed solely from what was *known* at t after the denylist has
   stripped final-history fields (Review-03, §6.4):
   - a detection is known iff it was delivered by an alert with jd <= t — its own stamped alert, or the
     ``prv_candidates`` of the alert named by ``parent_candid``;
   - a non-detection is known iff a stamped alert of the object has mjd in [nd.mjd, min(t, nd.mjd + 30 d)];
   - per-alert ``i:jdstarthist`` / ``i:ndethist`` from Fink rows with jd <= t are values the packet carried then.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time

from cosmic_triage.contracts.units import jd_to_mjd
from cosmic_triage.ingest import AlerceClient, FinkClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.ingest.fink import SCORE_COLUMNS
from cosmic_triage.replay.denylist import Denylist
from cosmic_triage.settings import load_config


@dataclass(frozen=True)
class PrefilterConfig:
    version: str
    window_days: float
    min_detections: int
    min_separation_min: float
    min_drb: float
    require_positive_subtraction: bool
    max_mag: float
    star_max_dist: float
    star_min_sgscore: float
    bright_star_max_dist: float
    bright_star_max_mag: float
    min_abs_gal_b: float
    scored_peak_mag: float
    config_hash: str
    packet_history_days: float = 30.0

    @classmethod
    def load(cls, path: str = "configs/replay/prefilter.yaml") -> PrefilterConfig:
        c, h = load_config(path)
        return cls(
            version=str(c["version"]), window_days=float(c["window_days"]), min_detections=int(c["min_detections"]),
            min_separation_min=float(c["min_separation_min"]), min_drb=float(c["min_drb"]),
            require_positive_subtraction=bool(c["require_positive_subtraction"]), max_mag=float(c["max_mag"]),
            star_max_dist=float(c["star_counterpart"]["max_dist_arcsec"]),
            star_min_sgscore=float(c["star_counterpart"]["min_sgscore"]),
            bright_star_max_dist=float(c["bright_star"]["max_dist_arcsec"]),
            bright_star_max_mag=float(c["bright_star"]["max_mag"]),
            min_abs_gal_b=float(c["min_abs_gal_b"]), scored_peak_mag=float(c["scored_peak_mag"]), config_hash=h,
            packet_history_days=float(c["packet_history_days"]),
        )


def night_t(night: str, decision_time_utc_hour: float = 20.0) -> float:
    """Decision time t (MJD) for the night beginning on local calendar date ``night`` (YYYY-MM-DD)."""
    return float(Time(f"{night}T00:00:00", scale="utc").mjd) + decision_time_utc_hour / 24.0


def night_ids(start: str, n: int) -> list[str]:
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _positive(x: Any) -> bool | None:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    return str(x).lower() in ("t", "1", "true")


def _candid(x: Any) -> str | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return str(int(x)) if isinstance(x, int | float) else str(x)


@dataclass
class RawCandidate:
    """Raw, denylist-scrubbed broker records for one object (all epochs). Never read these directly for a decision
    at t: use the ``known_*`` / ``*_le`` accessors, which apply the known-at-t rule."""

    oid: str
    detections: list[dict[str, Any]]
    non_detections: list[dict[str, Any]]
    fink_rows: list[dict[str, Any]]
    static: dict[str, Any] = field(default_factory=dict)
    _alerts: tuple[dict[str, float], list[float]] | None = field(default=None, init=False, repr=False, compare=False)

    def _alert_index(self) -> tuple[dict[str, float], list[float]]:
        """candid -> mjd for every stamped alert of the object (ALeRCE has_stamp detections and Fink alert rows),
        plus the sorted alert mjds. Built over all epochs; callers compare against t."""
        if self._alerts is None:
            by_candid: dict[str, float] = {}
            for d in self.detections:
                if d.get("has_stamp") and (c := _candid(d.get("candid"))) is not None:
                    by_candid[c] = float(d["mjd"])
            for r in self.fink_rows:
                if (c := _candid(r.get("i:candid"))) is not None:
                    by_candid.setdefault(c, float(r["mjd"]))
            self._alerts = (by_candid, sorted(set(by_candid.values())))
        return self._alerts

    def delivered_by(self, d: dict[str, Any]) -> float | None:
        """MJD of the alert that delivered detection ``d``: its own (stamped) alert, else its prv_candidates parent."""
        if d.get("has_stamp"):
            return float(d["mjd"])
        return self._alert_index()[0].get(_candid(d.get("parent_candid")) or "")

    def known_dets(self, t: float) -> list[dict[str, Any]]:
        """Detections known at t: mjd <= t and delivered by an alert with jd <= t (Review-03 known-at-t rule)."""
        out = []
        for d in self.detections:
            if d["mjd"] > t:
                continue
            by = self.delivered_by(d)
            if by is not None and by <= t:
                out.append(d)
        return out

    def nondet_delivered_by(self, n: dict[str, Any], t: float, history_days: float) -> float | None:
        """Earliest stamped alert with mjd in [nd.mjd, min(t, nd.mjd + history_days)], i.e. a packet that carried it."""
        mjds = self._alert_index()[1]
        i = bisect.bisect_left(mjds, float(n["mjd"]))
        if i < len(mjds) and mjds[i] <= min(t, float(n["mjd"]) + history_days):
            return mjds[i]
        return None

    def known_nondets(self, t: float, history_days: float) -> list[dict[str, Any]]:
        return [n for n in self.non_detections if n["mjd"] <= t and self.nondet_delivered_by(n, t, history_days) is not None]

    def qualifying(self, t: float, cfg: PrefilterConfig) -> list[dict[str, Any]]:
        out = []
        for d in self.known_dets(t):
            drb = _f(d.get("drb"))
            if drb is None or drb < cfg.min_drb:
                continue
            if cfg.require_positive_subtraction and _positive(d.get("isdiffpos")) is False:
                continue
            if _f(d.get("magpsf")) is None:
                continue
            out.append(d)
        return out

    def fink_le(self, t: float) -> list[dict[str, Any]]:
        return sorted((r for r in self.fink_rows if r["mjd"] <= t), key=lambda r: r["mjd"])

    def first_fink_le(self, t: float) -> dict[str, Any] | None:
        rows = self.fink_le(t)
        return rows[0] if rows else None

    def alert_hist_start(self, t: float) -> float | None:
        """Earliest per-alert ``i:jdstarthist`` (as MJD) over Fink rows with jd <= t; values > the row's jd are ignored."""
        vals = [jd_to_mjd(v) for r in self.fink_le(t) if (v := _f(r.get("i:jdstarthist"))) is not None
                and jd_to_mjd(v) <= r["mjd"]]
        return min(vals) if vals else None

    def alert_ndethist(self, t: float) -> int | None:
        vals = [int(v) for r in self.fink_le(t) if (v := _f(r.get("i:ndethist"))) is not None]
        return max(vals) if vals else None

    def alert_span_min(self, t: float) -> float | None:
        """Largest (alert jd - i:jdstarthist) over Fink rows <= t, in minutes (the BTS filter's history span)."""
        vals = [(r["mjd"] - jd_to_mjd(v)) * 1440.0 for r in self.fink_le(t) if (v := _f(r.get("i:jdstarthist"))) is not None
                and jd_to_mjd(v) <= r["mjd"]]
        return max(vals) if vals else None

    def position_le(self, t: float) -> tuple[float, float] | None:
        ds = [d for d in self.known_dets(t) if _f(d.get("ra")) is not None and _f(d.get("dec")) is not None]
        if not ds:
            return None
        ra = [float(d["ra"]) for d in ds]
        # Mean RA with wraparound handling.
        x = sum(math.cos(math.radians(r)) for r in ra)
        y = sum(math.sin(math.radians(r)) for r in ra)
        mra = math.degrees(math.atan2(y, x)) % 360.0
        return mra, sum(float(d["dec"]) for d in ds) / len(ds)

    def static_context(self, t: float) -> dict[str, float | None]:
        """Star / Gaia neighbour context from the first alert <= t (Fink), else the superset's static PS1 fields."""
        first = self.first_fink_le(t)
        ctx: dict[str, float | None] = {}
        for k in ("sgscore1", "distpsnr1", "srmag1", "neargaia", "maggaia"):
            v = _f(first.get(f"i:{k}")) if first is not None else None
            ctx[k] = v if v is not None else _f(self.static.get(k))
        return ctx


def _icrs_to_galactic_matrix() -> np.ndarray:
    """Rotation matrix ICRS -> Galactic, derived once from astropy (rows = Galactic x/y/z axes in ICRS)."""
    axes = SkyCoord(x=[1.0, 0.0, 0.0], y=[0.0, 1.0, 0.0], z=[0.0, 0.0, 1.0], frame="icrs", representation_type="cartesian")
    g = axes.galactic.cartesian
    return np.vstack([g.x.value, g.y.value, g.z.value])


_ICRS2GAL = _icrs_to_galactic_matrix()


def galactic_b(ra: float, dec: float) -> float:
    """Galactic latitude (deg). Same result as astropy's SkyCoord(...).galactic.b, ~1000x faster per call."""
    r, d = math.radians(ra), math.radians(dec)
    v = np.array([math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d)])
    z = float(_ICRS2GAL[2] @ v)
    return math.degrees(math.asin(max(-1.0, min(1.0, z))))


@dataclass(frozen=True)
class FilterResult:
    passed: bool
    reasons: tuple[str, ...]
    first_detection_mjd: float | None = None
    brightest_mag: float | None = None
    gal_b: float | None = None
    n_hist: int | None = None
    first_from_alert_history: bool = False


def evaluate(raw: RawCandidate, t: float, cfg: PrefilterConfig) -> FilterResult:
    """The time-honest pre-filter at t. Reads only what was known at t (see module docstring)."""
    reasons: list[str] = []
    dets = raw.known_dets(t)
    if not dets:
        return FilterResult(False, ("no_detection_le_t",))
    first_det = min(d["mjd"] for d in dets)
    hist_start = raw.alert_hist_start(t)
    first = min(first_det, hist_start) if hist_start is not None else first_det
    if first < t - cfg.window_days:
        reasons.append("first_detection_before_window")
    # Mirrors the BTS alert filter: the *alert* must pass drb (and the magnitude cut), while the detection count
    # and time span come from the position's history: known positive detections <= t, or the alert packet's own
    # i:ndethist / (jd - i:jdstarthist) from rows <= t, whichever is larger.
    q = raw.qualifying(t, cfg)
    hist = [d for d in dets if _positive(d.get("isdiffpos")) is not False and _f(d.get("magpsf")) is not None]
    n_hist = max(len(hist), raw.alert_ndethist(t) or 0)
    span = (max(d["mjd"] for d in hist) - min(d["mjd"] for d in hist)) * 1440.0 if hist else 0.0
    span = max(span, raw.alert_span_min(t) or 0.0)
    if not q:
        reasons.append("no_real_alert_le_t")
    if n_hist < cfg.min_detections:
        reasons.append("too_few_detections")
    elif span < cfg.min_separation_min:
        reasons.append("detections_too_close_in_time")
    brightest = min((float(d["magpsf"]) for d in q), default=None)
    if brightest is None or brightest > cfg.max_mag:
        reasons.append("fainter_than_max_mag")
    ctx = raw.static_context(t)
    sg, dps, srm = ctx["sgscore1"], ctx["distpsnr1"], ctx["srmag1"]
    if sg is not None and dps is not None and sg >= cfg.star_min_sgscore and dps < cfg.star_max_dist:
        reasons.append("star_like_counterpart")
    if (srm is not None and dps is not None and 0 < srm < cfg.bright_star_max_mag and dps < cfg.bright_star_max_dist) or (
        ctx["maggaia"] is not None and ctx["neargaia"] is not None
        and 0 < ctx["maggaia"] < cfg.bright_star_max_mag and ctx["neargaia"] < cfg.bright_star_max_dist
    ):
        reasons.append("near_bright_star")
    pos = raw.position_le(t)
    b = galactic_b(*pos) if pos else None
    if b is None or abs(b) < cfg.min_abs_gal_b:
        reasons.append("galactic_plane")
    return FilterResult(not reasons, tuple(reasons), first, brightest, b, n_hist,
                        hist_start is not None and hist_start < first_det)


def normalise_alerce_lightcurve(lc: dict[str, Any], deny: Denylist) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dets = []
    seen: set[str] = set()
    for d in lc.get("detections", []):
        if "has_stamp" not in d:
            raise ValueError("ALeRCE detection without has_stamp: the known-at-t delivery rule cannot be applied")
        d = deny.scrub(d)
        key = f"{d.get('candid')}:{d.get('mjd')}"
        if key in seen:
            continue
        seen.add(key)
        dets.append(d)
    nds = [deny.scrub(n) for n in lc.get("non_detections", [])]
    return sorted(dets, key=lambda d: d["mjd"]), sorted(nds, key=lambda n: n["mjd"])


def normalise_fink_rows(rows: Iterable[dict[str, Any]], deny: Denylist) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        jd = _f(r.get("i:jd"))
        if jd is None:
            continue
        if r.get("d:tag") == "upperlim":
            continue
        s = deny.scrub(r, source="fink")  # per-alert i:jdstarthist / i:ndethist are allowed in alert rows
        s["mjd"] = jd_to_mjd(jd)
        out.append(s)
    return sorted(out, key=lambda r: r["mjd"])


class ForwardPool:
    """Builds the forward pool for any decision time t from the cache (or the network when online)."""

    def __init__(
        self,
        alerce: AlerceClient,
        fink: FinkClient,
        alerce_db: AlerceDBClient,
        cfg: PrefilterConfig | None = None,
        deny: Denylist | None = None,
        workers: int = 6,
    ) -> None:
        self.alerce = alerce
        self.fink = fink
        self.alerce_db = alerce_db
        self.cfg = cfg or PrefilterConfig.load()
        self.deny = deny or Denylist.load()
        self.workers = workers
        self._raw: dict[str, RawCandidate] = {}
        self._superset_days: dict[int, dict[str, dict[str, Any]]] = {}

    # --- stage 1: superset -------------------------------------------------------------------------
    def superset_day(self, day_mjd: int) -> dict[str, dict[str, Any]]:
        if day_mjd in self._superset_days:
            return self._superset_days[day_mjd]
        rows = self.alerce_db.superset_day(
            day_mjd, self.cfg.max_mag, self.cfg.min_detections, self.cfg.star_min_sgscore, self.cfg.star_max_dist
        )
        keep = [r for r in rows if r["any_nonstellar_ps1"] and r["meanra"] is not None]
        out: dict[str, dict[str, Any]] = {}
        if keep:
            sc = SkyCoord(ra=[r["meanra"] for r in keep], dec=[r["meandec"] for r in keep], unit="deg").galactic
            for r, b in zip(keep, sc.b.deg, strict=True):
                if abs(float(b)) > self.cfg.min_abs_gal_b - 0.5:  # margin: the final mean position is not used later
                    out[r["oid"]] = {"sgscore1": r["sgscore1_min"], "distpsnr1": r["distpsnr1_min"], "srmag1": r["srmag1_min"]}
        self._superset_days[day_mjd] = out
        return out

    def superset(self, t: float) -> dict[str, dict[str, Any]]:
        """Superset for decision time t: objects first alerted in [floor(t - window), t]."""
        out: dict[str, dict[str, Any]] = {}
        for d in range(math.floor(t - self.cfg.window_days), math.floor(t) + 1):
            out.update(self.superset_day(d))
        return out

    # --- hydration -----------------------------------------------------------------------------------
    def hydrate(self, oid: str, static: dict[str, Any] | None = None) -> RawCandidate:
        if oid in self._raw:
            return self._raw[oid]
        dets, nds = normalise_alerce_lightcurve(self.alerce.lightcurve(oid), self.deny)
        rows = normalise_fink_rows(self.fink.object_rows(oid, with_upperlim=False, columns=SCORE_COLUMNS), self.deny)
        raw = RawCandidate(oid, dets, nds, rows, dict(static or {}))
        self._raw[oid] = raw
        return raw

    def hydrate_many(self, items: dict[str, dict[str, Any]]) -> dict[str, RawCandidate | Exception]:
        def one(oid: str) -> tuple[str, RawCandidate | Exception]:
            try:
                return oid, self.hydrate(oid, items[oid])
            except Exception as exc:  # recorded per object; the caller decides
                return oid, exc

        todo = sorted(items)
        if self.workers <= 1:
            return dict(one(o) for o in todo)
        with ThreadPoolExecutor(self.workers) as ex:
            return dict(ex.map(one, todo))

    # --- stage 2: time-honest filter -------------------------------------------------------------------
    def evaluate_all(self, t: float) -> dict[str, FilterResult]:
        sup = self.superset(t)
        hyd = self.hydrate_many(sup)
        errors = {o: e for o, e in hyd.items() if isinstance(e, Exception)}
        if errors:
            first = next(iter(errors.items()))
            raise RuntimeError(f"{len(errors)} objects failed to hydrate, e.g. {first[0]}: {first[1]}")
        return {oid: evaluate(raw, t, self.cfg) for oid, raw in hyd.items() if isinstance(raw, RawCandidate)}

    def candidates(self, t: float) -> list[str]:
        return sorted(oid for oid, r in self.evaluate_all(t).items() if r.passed)

    def raw(self, oid: str) -> RawCandidate:
        return self._raw[oid]
