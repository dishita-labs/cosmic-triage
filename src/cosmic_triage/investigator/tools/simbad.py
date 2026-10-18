"""SIMBAD cone (static catalogue) with an as-of filter for entries the transient itself may have created.

As-of rules: (1) transient-type entries (SN*, novae, ...) and transient designations (SN/AT/ZTF/ATLAS/... 20xx) are
dropped — they are reports, which belong to ``report_lookup`` with dates; (2) a redshift is kept only if its
reference (``rvz_bibcode``) was published in a year strictly before t's year, and the evidence is then dated to the
start of that year; otherwise the row is kept without its redshift (static, ``source_date`` None).
"""

from __future__ import annotations

import math
import re

from astropy.time import Time
from pydantic import BaseModel

from cosmic_triage.contracts.base import Contract
from cosmic_triage.contracts.evidence import Evidence
from cosmic_triage.ingest.catalogs import SimbadClient
from cosmic_triage.ingest.errors import ExternalAPIError, NetworkDisabled, OfflineCacheMiss
from cosmic_triage.investigator.tools.base import (
    LedgerView,
    ToolContext,
    ToolResult,
    ToolUnavailable,
    ToolUpstreamError,
    make_evidence,
)

TRANSIENT_OTYPES = {"SN", "SN*", "Candidate_SN*", "SN?", "Nova", "No*", "Nova?", "NL*", "TDE", "GRB", "Transient", "Ev?"}
TRANSIENT_NAME = re.compile(r"^(SN|AT|ZTF|ATLAS|ASASSN|ASAS-SN|PS\d?|Gaia\d{2}|GOTO|TCP|PNV|MASTER|LSQ|PTF|iPTF|DES)\s?-?\d{2}",
                            re.IGNORECASE)


def _f(x: object) -> float | None:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


class SimbadInput(Contract):
    ra: float
    dec: float
    radius_arcsec: float


class SimbadRow(Contract):
    main_id: str
    otype: str
    sep_arcsec: float
    redshift: float | None


class SimbadOutput(Contract):
    rows: tuple[SimbadRow, ...]
    filtered_transients: int
    redshifts_dropped_post_t: int


class SimbadConeTool:
    name = "simbad_cone"
    description = "SIMBAD objects near the position (galaxies, AGN, stars), excluding entries created by transients."
    Input = SimbadInput
    Output = SimbadOutput
    as_of_aware = True

    def __init__(self, simbad: SimbadClient, radius_arcsec: float = 10.0) -> None:
        self.simbad = simbad
        self.radius = radius_arcsec

    def build_input(self, ctx: ToolContext, ledger: LedgerView) -> BaseModel | None:
        return SimbadInput(ra=ctx.candidate.context.ra, dec=ctx.candidate.context.dec, radius_arcsec=self.radius)

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult:
        assert isinstance(inp, SimbadInput)
        try:
            raw = self.simbad.cone(inp.ra, inp.dec, inp.radius_arcsec, with_bibcode=True)
        except (OfflineCacheMiss, NetworkDisabled) as exc:
            raise ToolUnavailable(str(exc)) from None
        except ExternalAPIError as exc:
            raise ToolUpstreamError(str(exc)) from None
        t_year = int(Time(t_mjd, format="mjd").to_value("decimalyear"))
        rows: list[SimbadRow] = []
        evidence: list[Evidence] = []
        n_tr = n_z = 0
        for r in raw:
            name, otype = str(r.get("main_id", "")).strip(), str(r.get("otype", "")).strip()
            if otype in TRANSIENT_OTYPES or TRANSIENT_NAME.match(name):
                n_tr += 1
                continue
            ra, dec, sep = _f(r.get("ra")), _f(r.get("dec")), _f(r.get("sep_arcsec"))
            if ra is None or dec is None or sep is None:
                continue
            z, bib = _f(r.get("rvz_redshift")), str(r.get("rvz_bibcode") or "")
            date = None
            if z is not None:
                year = int(bib[:4]) if bib[:4].isdigit() else None
                if year is None or year >= t_year:
                    z, n_z = None, n_z + 1
                else:
                    date = float(Time(f"{year}-01-01T00:00:00", format="isot", scale="utc").mjd)
            rows.append(SimbadRow(main_id=name, otype=otype, sep_arcsec=sep, redshift=z))
            parsed = {"catalog": "SIMBAD", "main_id": name, "otype": otype, "ra": ra, "dec": dec, "sep_arcsec": sep, "redshift": z,
                      "redshift_bibcode": bib if z is not None else None}
            evidence.append(make_evidence("simbad", date, t_mjd, {"ra": inp.ra, "dec": inp.dec, "r": inp.radius_arcsec, "main_id": name},
                                          r, parsed))
        out = SimbadOutput(rows=tuple(rows), filtered_transients=n_tr, redshifts_dropped_post_t=n_z)
        return ToolResult(out, tuple(evidence), filtered_post_t=n_tr + n_z)
