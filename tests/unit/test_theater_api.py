"""Night Theater S0 frames (astropy, 5-min cadence), determinism, and the presentation-only API."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from cosmic_triage.contracts import NightFrame, RunConfig, RunManifest, Snapshot, TheaterNight
from cosmic_triage.replay.theater import build_night
from cosmic_triage.schedule.visibility import Site, altaz_grid, night_edges, sun_moon_track, twilight_label
from cosmic_triage.settings import load_config
from tests.contracts.examples import CS

T = 60766.8333333  # 2025-04-01 20:00 UTC
SITE = Site.from_facility(load_config("configs/facilities/palomar_sedm.yaml")[0])


def snapshot() -> Snapshot:
    cands = []
    for k, (ra, dec) in enumerate([(150.0, 20.0), (210.0, 45.0), (300.0, -10.0)]):
        ctx = CS.context.model_copy(update={"ra": ra, "dec": dec})
        ph = tuple(p.model_copy(update={"mjd": T - 2 + 0.1 * i}) for i, p in enumerate(CS.photometry))
        cands.append(CS.model_copy(update={"oid": f"ZTF25test{k}", "t_mjd": T, "context": ctx, "photometry": ph,
                                           "fink_rows": (), "stamp_prior": None}))
    return Snapshot(t_mjd=T, night_id="2025-04-01", candidates=tuple(cands), pool_config_hash="p", denylist_version="d", sources={})


def test_night_edges_order_and_plausibility() -> None:
    e = night_edges(SITE, T)
    assert T < e.sunset < e.astro_dusk < e.astro_dawn < e.sunrise < T + 1
    # Palomar, early April: sunset ~19:10 PDT = 02:10 UTC; sunrise ~06:35 PDT = 13:35 UTC.
    assert abs((e.sunset % 1) * 24 - 2.2) < 0.5
    assert abs((e.sunrise % 1) * 24 - 13.6) < 0.5


def test_twilight_labels() -> None:
    assert [twilight_label(a) for a in (5, -3, -9, -15, -30)] == ["day", "civil", "nautical", "astro", "night"]


def test_frames_cadence_and_content() -> None:
    header, frames = build_night(snapshot(), SITE, "run-x", "bench", "cfg", 30.0, "America/Los_Angeles")
    ts = np.array([f.t_mjd for f in frames])
    assert np.allclose(np.diff(ts) * 1440, 5.0, atol=1e-6)
    assert header.n_frames == len(frames) and header.n_candidates == 3
    assert ts[0] < header.sunset_mjd and ts[-1] > header.sunrise_mjd
    assert {f.twilight for f in frames} == {"day", "civil", "nautical", "astro", "night"}
    assert all(-90 <= c.alt <= 90 and 0 <= c.az < 360 for f in frames for c in f.candidates)
    assert all(f.facility.sim_level == "L1" and f.facility.state == "idle" for f in frames)
    assert all(not c.is_real_detection_now and c.belief_top is None for f in frames for c in f.candidates)


def test_frames_match_direct_astropy() -> None:
    _header, frames = build_night(snapshot(), SITE, "run-x", "bench", "cfg")
    f = frames[len(frames) // 2]
    sm = sun_moon_track(SITE, np.array([f.t_mjd]))
    alt, _az = altaz_grid(SITE, np.array([150.0]), np.array([20.0]), np.array([f.t_mjd]))
    assert f.sun_alt == pytest.approx(float(sm["sun_alt"][0]), abs=1e-3)
    assert f.candidates[0].alt == pytest.approx(float(alt[0, 0]), abs=1e-3)


def test_frames_deterministic() -> None:
    a = build_night(snapshot(), SITE, "run-x", "bench", "cfg")
    b = build_night(snapshot(), SITE, "run-x", "bench", "cfg")
    assert json.dumps([x.model_dump() for x in a[1]]) == json.dumps([x.model_dump() for x in b[1]])
    assert a[0] == b[0]


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    snap = snapshot()
    header, frames = build_night(snap, SITE, "run-x", "bench", "cfg", 30.0, "America/Los_Angeles")
    d = tmp_path / "bench" / "2025-04-01" / "run-x"
    (d / "snapshots").mkdir(parents=True)
    (d / "theater").mkdir()
    (d / "pool").mkdir()
    (d / "snapshots" / "2025-04-01.json").write_text(snap.model_dump_json())
    (d / "theater" / "2025-04-01.json").write_text(json.dumps({"header": header.model_dump(), "frames": [f.model_dump() for f in frames]}))
    (d / "pool" / "2025-04-01.json").write_text(json.dumps({"night": "2025-04-01", "t_mjd": T, "candidates": [{"oid": c.oid} for c in snap.candidates]}))
    cfg = RunConfig(run_id="run-x", mode="bench", seed=0, config_hash="cfg", code_version="test", script="test")
    (d / "manifest.json").write_text(RunManifest(config=cfg, output_hash="h").model_dump_json())
    return tmp_path


def test_api_serves_artifacts(runs_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cosmic_triage.api.app as appmod

    monkeypatch.setattr(appmod, "RUNS", runs_dir)
    c = TestClient(appmod.app)
    runs = c.get("/api/runs").json()
    assert runs[0]["run_id"] == "run-x" and runs[0]["nights"] == ["2025-04-01"]
    nights = c.get("/theater/nights").json()
    assert nights[0]["n_candidates"] == 3
    fr = c.get("/theater/run-x/2025-04-01/frames").json()
    TheaterNight.model_validate(fr["header"])
    NightFrame.model_validate(fr["frames"][0])
    assert c.get("/theater/run-x/2025-04-01/events").json() == []
    cand = c.get("/api/runs/run-x/nights/2025-04-01/candidates/ZTF25test1").json()
    assert cand["candidate"]["oid"] == "ZTF25test1" and all(p["mjd"] <= T for p in cand["candidate"]["photometry"])
    assert c.get("/api/runs/nope/nights/2025-04-01/candidates").status_code == 404
    assert c.get("/api/runs/run-x/nights/2025-04-01/candidates/ZTF00none").status_code == 404
