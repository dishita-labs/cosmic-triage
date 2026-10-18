"""Alert-history tool: summarises the candidate's Snapshot photometry and alert-time Fink fields (all <= t)."""

from __future__ import annotations

from pydantic import BaseModel

from cosmic_triage.contracts import CandidateState
from cosmic_triage.contracts.base import Contract
from cosmic_triage.investigator.tools.base import LedgerView, ToolContext, ToolResult, make_evidence


class HistoryInput(Contract):
    candidate: CandidateState


class HistoryOutput(Contract):
    n_detections: int
    n_nondetections: int
    first_detection_mjd: float
    last_detection_mjd: float
    brightest_mag: float
    latest_mag: float
    latest_band: str
    alert_hist_start_mjd: float | None
    alert_ndethist: int | None
    latest_snn_snia_vs_nonia: float | None
    latest_snn_sn_vs_all: float | None
    latest_cdsxmatch: str | None
    tns_label_at_alert_time: str | None
    tns_label_first_mjd: float | None


class AlertHistoryTool:
    name = "alert_history"
    description = "Summarise detections, non-detections and alert-time broker fields known at t (Snapshot only)."
    Input = HistoryInput
    Output = HistoryOutput
    as_of_aware = True

    def build_input(self, ctx: ToolContext, ledger: LedgerView) -> BaseModel | None:
        return HistoryInput(candidate=ctx.candidate)

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult:
        assert isinstance(inp, HistoryInput)
        c = inp.candidate
        phot = [p for p in c.photometry if p.mjd <= t_mjd]
        rows = sorted((r for r in c.fink_rows if r.mjd <= t_mjd), key=lambda r: r.mjd)
        hist_starts = [r.hist_start_mjd for r in rows if r.hist_start_mjd is not None]
        ndets = [r.hist_ndet for r in rows if r.hist_ndet is not None]
        tns = next((r for r in rows if r.tns_alert_time not in (None, "", "nan", "None")), None)
        latest = rows[-1] if rows else None
        out = HistoryOutput(
            n_detections=c.n_detections, n_nondetections=c.n_nondetections, first_detection_mjd=c.first_detection_mjd,
            last_detection_mjd=c.last_detection_mjd, brightest_mag=c.brightest_mag, latest_mag=c.latest_mag,
            latest_band=c.latest_band, alert_hist_start_mjd=min(hist_starts) if hist_starts else None,
            alert_ndethist=max(ndets) if ndets else None,
            latest_snn_snia_vs_nonia=latest.snn_snia_vs_nonia if latest else None,
            latest_snn_sn_vs_all=latest.snn_sn_vs_all if latest else None,
            latest_cdsxmatch=latest.cdsxmatch if latest else None,
            tns_label_at_alert_time=tns.tns_alert_time if tns else None, tns_label_first_mjd=tns.mjd if tns else None,
        )
        query = {"oid": c.oid, "t_mjd": t_mjd}
        evidence = [make_evidence(
            "alerce", max(p.mjd for p in phot) if phot else None, t_mjd, {**query, "kind": "photometry_summary"},
            [p.model_dump() for p in phot],
            {"oid": c.oid, "ra": c.context.ra, "dec": c.context.dec, "n_detections": out.n_detections,
             "n_nondetections": out.n_nondetections, "first_detection_mjd": out.first_detection_mjd,
             "first_known_detection_mjd": min((p.mjd for p in phot if p.is_detection), default=None),
             "last_detection_mjd": out.last_detection_mjd, "brightest_mag": out.brightest_mag, "latest_mag": out.latest_mag,
             "latest_band": out.latest_band},
        )]
        if latest is not None:
            evidence.append(make_evidence(
                "fink", latest.mjd, t_mjd, {**query, "kind": "alert_fields"}, [r.model_dump() for r in rows],
                {"oid": c.oid, "alert_hist_start_mjd": out.alert_hist_start_mjd, "alert_ndethist": out.alert_ndethist,
                 "first_known_detection_mjd": min((p.mjd for p in phot if p.is_detection), default=None),
                 "latest_snn_snia_vs_nonia": out.latest_snn_snia_vs_nonia, "latest_snn_sn_vs_all": out.latest_snn_sn_vs_all,
                 "latest_cdsxmatch": out.latest_cdsxmatch},
            ))
        if tns is not None:
            # Fink's alert-time TNS label: the classification existed by this alert (date_kind = evidence_by, §6.4).
            evidence.append(make_evidence(
                "fink", tns.mjd, t_mjd, {**query, "kind": "tns_label_at_alert_time"}, tns.model_dump(),
                {"oid": c.oid, "tns_label": tns.tns_alert_time, "first_alert_mjd_with_label": tns.mjd, "alert_candid": tns.candid},
            ))
        return ToolResult(out, tuple(evidence), cache_hit=None)
