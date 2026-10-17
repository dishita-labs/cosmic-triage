"""Adversarial leakage fixtures (§10.3 M1): every planted future/truth datum must be absent or recomputed.

A failure here is a §14.8 stop condition — never weaken these tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cosmic_triage.contracts import Snapshot
from cosmic_triage.replay.clock import Clock, build_candidate
from cosmic_triage.replay.denylist import Denylist
from cosmic_triage.replay.pool import (
    ForwardPool,
    PrefilterConfig,
    RawCandidate,
    evaluate,
    normalise_alerce_lightcurve,
    normalise_fink_rows,
)

FIXDIR = Path(__file__).parent / "fixtures"
FIXTURES = sorted(FIXDIR.glob("*.json"))
DENY = Denylist.load()
CFG = PrefilterConfig.load()


def load(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text())


def to_raw(fx: dict[str, Any]) -> RawCandidate:
    r = fx["raw"]
    dets, nds = normalise_alerce_lightcurve(r["lightcurve"], DENY)
    return RawCandidate(r["oid"], dets, nds, normalise_fink_rows(r["fink_rows"], DENY), dict(r["static"]))


def walk(obj: Any, keys: set[str], values: list[Any]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            walk(v, keys, values)
    elif isinstance(obj, list | tuple):
        for v in obj:
            walk(v, keys, values)
    else:
        values.append(obj)


def test_at_least_twenty_fixtures() -> None:
    assert len(FIXTURES) >= 20


def test_required_fixtures_present() -> None:
    names = {load(p)["name"] for p in FIXTURES}
    assert {"detection_t_plus_0p01d", "fink_row_jd_after_t", "bts_type_field", "ndethist_final_history"} <= names


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture(path: Path) -> None:
    fx = load(path)
    t, exp = fx["t_mjd"], fx["expect"]
    raw = to_raw(fx)
    # The scrubbed raw records carry no denylisted key.
    for rec in raw.detections + raw.non_detections + raw.fink_rows:
        assert not [k for k in rec if DENY.denied(k)], rec
    res = evaluate(raw, t, CFG)
    if "member" in exp:
        assert res.passed is exp["member"], res.reasons
    if exp.get("no_snapshot"):
        with pytest.raises(ValueError):
            build_candidate(raw, t)
        return
    cand = build_candidate(raw, t)
    snap = Snapshot(t_mjd=t, night_id="2025-04-01", candidates=(cand,), pool_config_hash=CFG.config_hash,
                    denylist_version=DENY.version, sources={})
    dumped = json.loads(snap.model_dump_json())
    keys: set[str] = set()
    values: list[Any] = []
    walk(dumped, keys, values)
    text = snap.model_dump_json()
    # Universal invariants.
    assert all(p.mjd <= t for p in cand.photometry)
    assert all(r.mjd <= t for r in cand.fink_rows)
    assert not [k for k in keys if DENY.denied(k) and k not in ("ra", "dec")], keys
    # Fixture-specific expectations.
    for k in ("n_detections", "n_nondetections", "brightest_mag", "latest_mag", "latest_band", "first_detection_mjd"):
        if k in exp:
            assert getattr(cand, k) == pytest.approx(exp[k]) if isinstance(exp[k], float) else getattr(cand, k) == exp[k]
    if "n_fink_rows" in exp:
        assert len(cand.fink_rows) == exp["n_fink_rows"]
    if "ra" in exp:
        assert cand.context.ra == pytest.approx(exp["ra"], abs=1e-9)
        assert cand.context.dec == pytest.approx(exp["dec"], abs=1e-9)
    for s in exp.get("forbidden_strings", []):
        assert s not in text, f"leaked string {s!r}"
    for v in exp.get("forbidden_values", []):
        assert not [x for x in values if isinstance(x, int | float) and not isinstance(x, bool) and x == v], (
            f"leaked value {v!r}")
    for k in exp.get("forbidden_keys", []):
        assert k not in keys


class FixturePool(ForwardPool):
    """ForwardPool whose broker layer is replaced by the fixtures (exercises the full Clock path offline)."""

    def __init__(self, raws: dict[str, RawCandidate]) -> None:
        self.cfg = CFG
        self.deny = DENY
        self.workers = 1
        self._raw = dict(raws)
        self._superset_days = {}
        self._alerce_days = {}

    def superset(self, t: float) -> dict[str, dict[str, Any]]:
        return {o: {} for o in self._raw}


def test_clock_snapshot_over_all_fixtures() -> None:
    fxs = [load(p) for p in FIXTURES]
    t = fxs[0]["t_mjd"]
    assert all(f["t_mjd"] == t for f in fxs)
    raws = {f["raw"]["oid"]: to_raw(f) for f in fxs}
    snap = Clock(DENY).snapshot(t, FixturePool(raws))
    members = {c.oid for c in snap.candidates}
    for f in fxs:
        if "member" in f["expect"]:
            assert (f["raw"]["oid"] in members) is f["expect"]["member"], f["name"]
    text = snap.model_dump_json()
    for f in fxs:
        if f["raw"]["oid"] in members:
            for s in f["expect"].get("forbidden_strings", []):
                assert s not in text, (f["name"], s)
    assert snap.night_id == "2025-04-01"
