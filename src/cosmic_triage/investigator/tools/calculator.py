"""Offset / absolute-magnitude calculator (§4.1 #3 analysis tool). Pure code over cited ledger evidence.

M = m_brightest(<= t) - mu(z), Planck18 distance modulus; no K-correction or extinction (stated in the output).
The evidence is dated to the latest of its inputs (all <= t), so it can never be newer than what it was computed from.
"""

from __future__ import annotations

import math

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.cosmology import Planck18
from pydantic import BaseModel

from cosmic_triage.contracts.base import Contract
from cosmic_triage.investigator.tools.base import LedgerView, ToolContext, ToolInputError, ToolResult, make_evidence


class CalcInput(Contract):
    transient_ra: float
    transient_dec: float
    brightest_mag: float
    host_ra: float
    host_dec: float
    z: float
    z_kind: str
    history_evidence_id: str
    host_evidence_id: str
    input_dates: tuple[float, ...]


class CalcOutput(Contract):
    sep_arcsec: float
    distmod: float
    abs_mag: float
    z: float
    z_kind: str


def separation_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    return float(SkyCoord(ra1 * u.deg, dec1 * u.deg).separation(SkyCoord(ra2 * u.deg, dec2 * u.deg)).arcsec)


class OffsetAbsMagTool:
    name = "offset_absmag"
    description = "Offset from the host and absolute magnitude at the brightest point <= t, from a cited host redshift."
    Input = CalcInput
    Output = CalcOutput
    as_of_aware = True

    def build_input(self, ctx: ToolContext, ledger: LedgerView) -> BaseModel | None:
        entries = ledger.entries()
        hist = next((e for e in entries if e.source == "alerce" and e.query.get("kind") == "photometry_summary"), None)
        if hist is None:
            return None
        host = None
        for e in entries:  # preference: spectroscopic catalogue z (Sherlock), dated SIMBAD z, Sherlock photo-z
            p = e.parsed
            if e.source == "sherlock" and p.get("z") is not None and p.get("ra") is not None:
                host = (e, float(p["z"]), "spec", float(p["ra"]), float(p["dec"]))
                break
        if host is None:
            gals = [e for e in entries if e.source == "simbad" and e.parsed.get("redshift") is not None]
            if gals:
                e = min(gals, key=lambda x: float(x.parsed["sep_arcsec"]))
                host = (e, float(e.parsed["redshift"]), "spec", float(e.parsed["ra"]), float(e.parsed["dec"]))
        if host is None:
            e2 = next((e for e in entries if e.source == "sherlock" and e.parsed.get("photo_z") is not None
                       and e.parsed.get("ra") is not None), None)
            if e2 is not None:
                host = (e2, float(e2.parsed["photo_z"]), "photo", float(e2.parsed["ra"]), float(e2.parsed["dec"]))
        if host is None or host[1] <= 0:
            return None
        hp = hist.parsed
        dates = tuple(d for d in (hist.source_date, host[0].source_date) if d is not None)
        return CalcInput(transient_ra=float(hp["ra"]), transient_dec=float(hp["dec"]), brightest_mag=float(hp["brightest_mag"]),
                         host_ra=host[3], host_dec=host[4], z=host[1], z_kind=host[2], history_evidence_id=hist.id,
                         host_evidence_id=host[0].id, input_dates=dates)

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult:
        assert isinstance(inp, CalcInput)
        if not (0.0 < inp.z < 3.0) or not math.isfinite(inp.brightest_mag):
            raise ToolInputError(f"z={inp.z} or m={inp.brightest_mag} out of range")
        sep = separation_arcsec(inp.transient_ra, inp.transient_dec, inp.host_ra, inp.host_dec)
        mu = float(Planck18.distmod(inp.z).value)
        out = CalcOutput(sep_arcsec=round(sep, 4), distmod=round(mu, 4), abs_mag=round(inp.brightest_mag - mu, 4), z=inp.z,
                         z_kind=inp.z_kind)
        parsed = {"quantity": "abs_mag_at_brightest_le_t", "value": out.abs_mag, "unit": "mag", "m": inp.brightest_mag,
                  "z": inp.z, "z_kind": inp.z_kind, "distmod": out.distmod, "sep_arcsec": out.sep_arcsec, "cosmology": "Planck18",
                  "inputs": [inp.history_evidence_id, inp.host_evidence_id], "caveats": "no K-correction, no extinction"}
        date = max(inp.input_dates) if inp.input_dates else None
        return ToolResult(out, (make_evidence("tool", date, t_mjd, {"tool": self.name, "inputs": parsed["inputs"]},
                                              inp.model_dump(), parsed),))
