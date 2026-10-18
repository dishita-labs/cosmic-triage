"""Deterministic validator chain (§4.4): schema → provenance → date ≤ t → geometry → type-specific → support.

A draft becomes a ``Claim`` only if every check passes. Each check runs even after a failure so the trace shows the
full rejection profile. ``date_le_t`` is the hard leakage check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pydantic import ValidationError

from cosmic_triage.contracts import CandidateState, Claim, ClaimDraft, Evidence, ValidationCheck, ValidationReport
from cosmic_triage.investigator.tools.calculator import separation_arcsec
from cosmic_triage.investigator.validators.payloads import PAYLOADS
from cosmic_triage.investigator.validators.support import SupportVerifier

AGN_TYPES = {"AGN", "QSO", "Seyfert", "Seyfert_1", "Seyfert_2", "Blazar", "BLLac", "LINER", "Candidate_AGN", "Candidate_QSO",
             "SyG", "Sy1", "Sy2", "Bla", "BLL", "AG?", "Q?"}
STAR_TYPES = {"Star", "*", "V*", "EB*", "RRLyr", "CV*", "YSO", "Mira", "LPV*", "WD*", "PM*", "HighPM*", "low-mass*",
              "BYDra", "RSCVn", "Cepheid", "delSctV*", "TTau*", "Em*", "Be*", "Pulsating*", "EllipVar", "Candidate_EB*",
              "Candidate_CV*", "Candidate_RRLyr", "Candidate_YSO", "Variable*", "Irregular_V*", "RGB*", "C*", "S*"}
SHERLOCK_STAR = {"VS", "CV", "BS"}


@dataclass(frozen=True)
class ValidationConfig:
    support_threshold: float
    geometry_tolerance_arcsec: float
    z_min: float
    z_max: float
    radius: dict[str, float]


class Validator:
    def __init__(self, cfg: ValidationConfig, verifier: SupportVerifier) -> None:
        self.cfg = cfg
        self.verifier = verifier

    def validate(self, draft: ClaimDraft, ledger_entries: dict[str, Evidence], t_mjd: float, candidate: CandidateState,
                 run_id: str) -> tuple[ValidationReport, object | None]:
        checks: list[ValidationCheck] = []
        cited = [ledger_entries[i] for i in draft.evidence_ids if i in ledger_entries]
        # 1. schema
        payload_ok, detail = True, ""
        try:
            PAYLOADS[draft.kind].model_validate(draft.payload)
        except ValidationError as exc:
            payload_ok, detail = False, f"{exc.error_count()} schema error(s): {exc.errors()[0]['msg']}"
        checks.append(ValidationCheck(name="schema", passed=payload_ok, detail=detail))
        # 2. provenance: every cited id exists in this run's ledger, and at least one is cited
        missing = [i for i in draft.evidence_ids if i not in ledger_entries]
        checks.append(ValidationCheck(name="provenance", passed=bool(draft.evidence_ids) and not missing,
                                      detail=f"missing {missing}" if missing else ("no evidence cited" if not draft.evidence_ids else "")))
        # 3. date <= t (hard leakage check): cited evidence and any date in the payload
        late = [e.id for e in cited if (e.source_date is not None and e.source_date > t_mjd) or e.retrieved_at_sim_time != t_mjd]
        pdate = draft.payload.get("date_mjd")
        if isinstance(pdate, int | float) and pdate > t_mjd:
            late.append("payload.date_mjd")
        checks.append(ValidationCheck(name="date_le_t", passed=not late, detail=f"after t: {late}" if late else ""))
        # 4. geometry recomputed from source coordinates
        checks.append(self._geometry(draft, cited, candidate) if payload_ok else
                      ValidationCheck(name="geometry", passed=False, detail="schema failed"))
        # 5. type-specific
        checks.append(self._type_specific(draft, cited, t_mjd) if payload_ok else
                      ValidationCheck(name="type_specific", passed=False, detail="schema failed"))
        # 6. support
        score, call = self.verifier.score(draft, cited, run_id) if cited else (0.0, None)
        checks.append(ValidationCheck(name="support", passed=score >= self.cfg.support_threshold,
                                      detail=f"{self.verifier.name}={score:.3f} (τ={self.cfg.support_threshold})"))
        ok = all(c.passed for c in checks)
        return ValidationReport(accepted=ok, checks=tuple(checks), support_score=score,
                                rejected_reasons=tuple(f"{c.name}: {c.detail}" for c in checks if not c.passed)), call

    def _geometry(self, draft: ClaimDraft, cited: list[Evidence], cand: CandidateState) -> ValidationCheck:
        p = draft.payload
        if draft.kind in ("known_agn", "star_counterpart", "nuclear", "host_redshift"):
            ra, dec = (p["host_ra"], p["host_dec"]) if draft.kind == "host_redshift" else (p["ra"], p["dec"])
            src = [e for e in cited if e.parsed.get("ra") is not None and e.parsed.get("dec") is not None
                   and math.isclose(float(e.parsed["ra"]), float(ra), abs_tol=1e-6)
                   and math.isclose(float(e.parsed["dec"]), float(dec), abs_tol=1e-6)]
            if not src:
                return ValidationCheck(name="geometry", passed=False, detail="claimed coordinates not in any cited evidence")
            sep = separation_arcsec(cand.context.ra, cand.context.dec, float(ra), float(dec))
            lim = self.cfg.radius.get(draft.kind, math.inf)
            claimed = float(p["sep_arcsec"])
            if abs(sep - claimed) > max(self.cfg.geometry_tolerance_arcsec, 0.05 * sep):
                return ValidationCheck(name="geometry", passed=False, detail=f"claimed sep {claimed:.2f}″ vs recomputed {sep:.2f}″")
            if sep > lim:
                return ValidationCheck(name="geometry", passed=False, detail=f"recomputed sep {sep:.2f}″ > {lim}″ for {draft.kind}")
            return ValidationCheck(name="geometry", passed=True, detail=f"recomputed sep {sep:.2f}″")
        return ValidationCheck(name="geometry", passed=True, detail="not applicable")

    def _type_specific(self, draft: ClaimDraft, cited: list[Evidence], t_mjd: float) -> ValidationCheck:
        p = draft.payload
        def fail(d: str) -> ValidationCheck:
            return ValidationCheck(name="type_specific", passed=False, detail=d)

        if draft.kind == "prior_classification":
            if p["date_kind"] == "report_date":
                ok = [e for e in cited if e.source == "tns" and e.parsed.get("report_type") == "classification"
                      and e.parsed.get("tns_class") == p["tns_class"] and e.parsed.get("date_mjd") == p["date_mjd"]]
                if not ok:
                    return fail("report_date requires a cited TNS classification report with the same class and date")
            else:
                ok = [e for e in cited if e.source == "fink" and e.parsed.get("tns_label") == p["tns_class"]
                      and e.parsed.get("first_alert_mjd_with_label") == p["date_mjd"]]
                if not ok:
                    return fail("evidence_by requires a cited Fink alert-time d:tns label with the same class and alert date")
            if not str(p["tns_class"]).strip():
                return fail("empty class")
        elif draft.kind == "host_redshift":
            z = float(p["z"])
            if not (self.cfg.z_min <= z <= self.cfg.z_max):
                return fail(f"z={z} outside [{self.cfg.z_min}, {self.cfg.z_max}]")
            if z <= 0.0:
                return fail("z <= 0 is not a host-galaxy redshift measurement (catalogue placeholder)")
            key = "z" if p["z_kind"] == "spec" else "photo_z"
            if not any((e.parsed.get(key) == z) or (e.source == "simbad" and e.parsed.get("redshift") == z) for e in cited):
                return fail("redshift not present in cited evidence")
        elif draft.kind in ("known_agn", "star_counterpart", "nuclear"):
            types = {str(e.parsed.get("otype") or "") for e in cited if e.source == "simbad"}
            sh = {str(e.parsed.get("classification") or "") for e in cited if e.source == "sherlock"}
            if draft.kind == "known_agn" and not (types & AGN_TYPES or "AGN" in sh):
                return fail("no AGN-type source cited")
            if draft.kind == "star_counterpart" and not (types & STAR_TYPES or sh & SHERLOCK_STAR):
                return fail("no stellar source cited")
            if draft.kind == "nuclear" and not ("NT" in sh or any(e.parsed.get("catalogue_object_type") == "galaxy" for e in cited)
                                                 or any(t.startswith(("G", "Sy", "AGN", "QSO", "LINER")) for t in types)):
                return fail("no galaxy/nuclear association cited")
        elif draft.kind == "prior_flares":
            if p["basis"] == "alert_hist_start":
                ok = [e for e in cited if e.source == "fink" and e.parsed.get("alert_hist_start_mjd") == p["earlier_activity_mjd"]]
            else:
                ok = [e for e in cited if e.source == "tns" and e.parsed.get("report_type") == "discovery"
                      and e.parsed.get("date_mjd") == p["earlier_activity_mjd"] and e.parsed.get("tns_name") == p.get("ref")]
            first = [e for e in cited if e.parsed.get("first_known_detection_mjd") == p["first_known_detection_mjd"]]
            gap = float(p["first_known_detection_mjd"]) - float(p["earlier_activity_mjd"])
            if not ok or not first:
                return fail("earlier activity / first detection not in cited evidence")
            if float(p["earlier_activity_mjd"]) > t_mjd or abs(gap - float(p["gap_days"])) > 1e-3 or gap <= 0:
                return fail(f"inconsistent gap ({gap:.3f} d recomputed)")
        elif draft.kind == "analysis_result":
            if not any(e.source == "tool" for e in cited) or not math.isfinite(float(p["value"])):
                return fail("analysis results must cite a tool computation with a finite value")
        return ValidationCheck(name="type_specific", passed=True)


def to_claim(draft: ClaimDraft, report: ValidationReport) -> Claim:
    return Claim(kind=draft.kind, payload=draft.payload, evidence_ids=draft.evidence_ids, extractor_model=draft.extractor_model,
                 validation=report)
