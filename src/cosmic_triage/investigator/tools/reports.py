"""Report lookup: TNS bot (report dates) or the Lasair-TNS fallback (discovery only), as-of t (§4.1 #1, §6.4).

As-of rules at the tool layer:
- TNS bot: a report is returned only if its own date is <= t; the object's *current* type is never used undated.
- Lasair fallback: only the discovery report survives (``disc_date <= t``); ``type``, ``z``, ``tns_prefix`` (AT -> SN
  after classification), host fields, internal-name lists and modification dates describe the object *now* and are
  stripped. A classification date is not available from this path (Fink ``d:tns`` provides ``evidence_by`` instead).
"""

from __future__ import annotations

from typing import Any

from astropy.time import Time
from pydantic import BaseModel

from cosmic_triage.contracts.base import Contract
from cosmic_triage.contracts.evidence import Evidence
from cosmic_triage.ingest import LasairClient, TNSClient
from cosmic_triage.ingest.errors import CredentialMissing, ExternalAPIError, OfflineCacheMiss
from cosmic_triage.investigator.tools.base import (
    LedgerView,
    ToolContext,
    ToolResult,
    ToolUnavailable,
    ToolUpstreamError,
    make_evidence,
)

LASAIR_KEEP = ("tns_name", "disc_date", "disc_mag", "disc_mag_filter", "source_group", "sender", "ra", "decl")


def iso_to_mjd(s: str) -> float:
    return float(Time(s.replace(" ", "T"), format="isot", scale="utc").mjd)


class ReportInput(Contract):
    oid: str
    ra: float
    dec: float
    radius_arcsec: float


class Report(Contract):
    tns_name: str
    report_type: str
    date_mjd: float
    tns_class: str | None = None


class ReportOutput(Contract):
    mode: str
    reports: tuple[Report, ...]
    filtered_post_t: int


def _unwrap(data: Any) -> Any:
    return data.get("reply", data) if isinstance(data, dict) else data


class ReportLookupTool:
    name = "report_lookup"
    description = "TNS discovery/classification reports for the position, filtered to report date <= t."
    Input = ReportInput
    Output = ReportOutput
    as_of_aware = True

    def __init__(self, lasair: LasairClient, tns: TNSClient, radius_arcsec: float = 3.0) -> None:
        self.lasair = lasair
        self.tns = tns
        self.radius = radius_arcsec

    def build_input(self, ctx: ToolContext, ledger: LedgerView) -> BaseModel | None:
        c = ctx.candidate
        return ReportInput(oid=c.oid, ra=c.context.ra, dec=c.context.dec, radius_arcsec=self.radius)

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult:
        assert isinstance(inp, ReportInput)
        try:
            if TNSClient.credentials_present():
                return self._tns(inp, t_mjd)
            return self._lasair(inp, t_mjd)
        except (CredentialMissing, OfflineCacheMiss) as exc:
            raise ToolUnavailable(str(exc)) from None
        except ExternalAPIError as exc:
            raise ToolUpstreamError(str(exc)) from None

    def _lasair(self, inp: ReportInput, t_mjd: float) -> ToolResult:
        rows = self.lasair.tns_crossmatch(inp.oid)
        reports: list[Report] = []
        evidence: list[Evidence] = []
        dropped = 0
        for r in rows:
            if not r.get("disc_date") or not r.get("tns_name"):
                continue
            d = iso_to_mjd(str(r["disc_date"]))
            if d > t_mjd:
                dropped += 1
                continue
            kept = {k: r.get(k) for k in LASAIR_KEEP}
            parsed = {"report_type": "discovery", "via": "lasair.crossmatch_tns", "tns_name": str(r["tns_name"]),
                      "date_mjd": d, "ra": kept["ra"], "dec": kept["decl"], "disc_mag": kept["disc_mag"],
                      "disc_mag_filter": kept["disc_mag_filter"], "source_group": kept["source_group"]}
            reports.append(Report(tns_name=str(r["tns_name"]), report_type="discovery", date_mjd=d))
            evidence.append(make_evidence("tns", d, t_mjd, {"oid": inp.oid, "via": "lasair.crossmatch_tns"}, kept, parsed))
        return ToolResult(ReportOutput(mode="lasair_fallback", reports=tuple(reports), filtered_post_t=dropped),
                          tuple(evidence), cache_hit=None, filtered_post_t=dropped)

    def _tns(self, inp: ReportInput, t_mjd: float) -> ToolResult:
        # UNVERIFIED until TNS bot credentials are configured (kill-test #1): parsing is defensive.
        found = _unwrap(self.tns.search(inp.ra, inp.dec, inp.radius_arcsec)) or []
        reports: list[Report] = []
        evidence: list[Evidence] = []
        dropped = 0
        for hit in found if isinstance(found, list) else []:
            name = str(hit.get("objname") or "")
            if not name:
                continue
            obj = _unwrap(self.tns.get_object(name)) or {}
            disc = obj.get("discoverydate")
            if disc:
                d = iso_to_mjd(str(disc))
                if d <= t_mjd:
                    reports.append(Report(tns_name=name, report_type="discovery", date_mjd=d))
                    evidence.append(make_evidence("tns", d, t_mjd, {"objname": name, "via": "tns_bot"}, {"discoverydate": disc},
                                                  {"report_type": "discovery", "via": "tns_bot", "tns_name": name, "date_mjd": d}))
                else:
                    dropped += 1
            for rep in _classification_reports(obj):
                if rep["date_mjd"] > t_mjd:
                    dropped += 1
                    continue
                reports.append(Report(tns_name=name, report_type="classification", date_mjd=rep["date_mjd"], tns_class=rep["class"]))
                evidence.append(make_evidence("tns", rep["date_mjd"], t_mjd, {"objname": name, "via": "tns_bot"}, rep["raw"],
                                              {"report_type": "classification", "via": "tns_bot", "tns_name": name,
                                               "date_mjd": rep["date_mjd"], "tns_class": rep["class"]}))
        return ToolResult(ReportOutput(mode="tns_bot", reports=tuple(reports), filtered_post_t=dropped), tuple(evidence),
                          cache_hit=None, filtered_post_t=dropped)


def _classification_reports(obj: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key in ("classification_reports", "classifications", "classification"):
        reps = obj.get(key)
        if not isinstance(reps, list):
            continue
        for rep in reps:
            if not isinstance(rep, dict):
                continue
            when = rep.get("time_received") or rep.get("report_date") or rep.get("date")
            cls = rep.get("object_type") or rep.get("classification") or rep.get("type")
            if isinstance(cls, dict):
                cls = cls.get("name")
            if when and cls:
                out.append({"date_mjd": iso_to_mjd(str(when)), "class": str(cls), "raw": rep})
    return out
