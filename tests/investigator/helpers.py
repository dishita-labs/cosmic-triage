"""Shared builders for Investigator tests (offline, no network)."""

from __future__ import annotations

from typing import Any

from cosmic_triage.contracts import CandidateContext, CandidateState, FinkAlertRow, PhotometryPoint, Snapshot

T = 60787.8333333  # 2025-04-22 20:00 UTC
RA, DEC = 219.4997, 14.4549


def candidate(oid: str = "ZTF25testabc", t: float = T, tns: dict[float, str] | None = None, ra: float = RA, dec: float = DEC,
              snn: float = 0.6) -> CandidateState:
    phot = (
        PhotometryPoint(mjd=t - 5.0, band="r", is_detection=True, mag=18.6, drb=0.99, isdiffpos=True, candid="111",
                        delivered_by_mjd=t - 5.0),
        PhotometryPoint(mjd=t - 2.0, band="g", is_detection=True, mag=18.1, drb=0.99, isdiffpos=True, candid="222",
                        delivered_by_mjd=t - 2.0),
        PhotometryPoint(mjd=t - 8.0, band="r", is_detection=False, limiting_mag=20.3, delivered_by_mjd=t - 5.0),
    )
    tns = tns or {}
    rows = tuple(FinkAlertRow(mjd=m, candid=c, snn_snia_vs_nonia=snn, snn_sn_vs_all=0.7, cdsxmatch="Unknown",
                              tns_alert_time=tns.get(m, ""), hist_start_mjd=t - 5.0, hist_ndet=2)
                 for m, c in ((t - 5.0, "111"), (t - 2.0, "222")))
    return CandidateState(oid=oid, t_mjd=t, context=CandidateContext(ra=ra, dec=dec, gal_b=60.0), photometry=phot, fink_rows=rows,
                          first_detection_mjd=t - 5.0, last_detection_mjd=t - 2.0, n_detections=2, n_nondetections=1,
                          brightest_mag=18.1, latest_mag=18.1, latest_band="g")


def snapshot(*cands: CandidateState, t: float = T) -> Snapshot:
    return Snapshot(t_mjd=t, night_id="2025-04-22", candidates=cands, pool_config_hash="test", denylist_version="test", sources={})


class FakeLasair:
    def __init__(self, tns_rows: list[dict[str, Any]] | None = None, sherlock_rows: list[dict[str, Any]] | None = None) -> None:
        self.tns_rows = tns_rows or []
        self.sherlock_rows = sherlock_rows or []
        self.calls = 0

    def tns_crossmatch(self, oid: str) -> list[dict[str, Any]]:
        self.calls += 1
        return self.tns_rows

    def sherlock_object(self, oid: str) -> list[dict[str, Any]]:
        self.calls += 1
        return self.sherlock_rows


class FakeSimbad:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def cone(self, ra: float, dec: float, radius_arcsec: float = 10.0, top: int = 25, with_bibcode: bool = False) -> list[dict[str, Any]]:
        return self.rows


class FakeTNS:
    @staticmethod
    def credentials_present() -> bool:
        return False
