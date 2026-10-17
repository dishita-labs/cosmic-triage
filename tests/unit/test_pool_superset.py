"""ForwardPool stage-1 superset: necessary conditions only (monotone or static), applied per alert day."""

from __future__ import annotations

from typing import Any

from cosmic_triage.replay.pool import ForwardPool, PrefilterConfig


class StubDB:
    def __init__(self, rows: dict[int, list[dict[str, Any]]]) -> None:
        self.rows = rows
        self.calls: list[int] = []

    def superset_day(self, day_mjd: int, max_mag: float, min_ndet: int, star_sg: float, star_dist: float) -> list[dict[str, Any]]:
        self.calls.append(day_mjd)
        assert (max_mag, min_ndet, star_sg, star_dist) == (19.0, 2, 0.5, 2.0)  # passed straight from the config
        return self.rows.get(day_mjd, [])


def row(oid: str, ra: float, dec: float, nonstellar: bool = True) -> dict[str, Any]:
    return {"oid": oid, "firstmjd": 0.0, "meanra": ra, "meandec": dec, "any_nonstellar_ps1": nonstellar,
            "sgscore1_min": 0.1, "distpsnr1_min": 3.0, "srmag1_min": 20.0}


def test_superset_window_and_static_cuts() -> None:
    db = StubDB({
        60752: [row("ZTFa", 185.0, 30.0)],
        60760: [row("ZTFb", 185.0, 30.0), row("ZTFstar", 185.0, 30.0, nonstellar=False), row("ZTFplane", 266.4, -28.9)],
        60766: [row("ZTFc", 150.0, 20.0)],
        60767: [row("ZTFfuture", 150.0, 20.0)],
    })
    pool = ForwardPool(None, None, db, cfg=PrefilterConfig.load())  # type: ignore[arg-type]
    sup = pool.superset(60766.8333)
    assert set(sup) == {"ZTFa", "ZTFb", "ZTFc"}  # star-like, Galactic-centre and after-t days excluded
    assert min(db.calls) == 60752 and max(db.calls) == 60766
    assert sup["ZTFb"] == {"sgscore1": 0.1, "distpsnr1": 3.0, "srmag1": 20.0}  # static context only, no final aggregates
