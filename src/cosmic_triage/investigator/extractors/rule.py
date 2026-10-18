"""RuleExtractor: deterministic ClaimDrafts from structured tool evidence (§10.3 M2 Review-03; ablation baseline).

Rules are conservative and cite exactly the evidence they read. Every draft still goes through the validator chain.
"""

from __future__ import annotations

from typing import Any

from cosmic_triage.contracts import ClaimDraft, Evidence
from cosmic_triage.contracts.evidence import ClaimKind
from cosmic_triage.investigator.validators.chain import AGN_TYPES, SHERLOCK_STAR, STAR_TYPES

EXTRACTOR_ID = "rule-v1"
PRIOR_FLARE_GAP_DAYS = 30.0        # alert-time history start this long before the first known detection
PRIOR_TNS_GAP_DAYS = 365.0         # an earlier TNS discovery at the position this long before
COUNTERPART_RADIUS = 1.5
NUCLEAR_RADIUS = 0.5               # offset from a catalogued galaxy's centre treated as nuclear
HOST_RADIUS = 60.0


def _draft(kind: ClaimKind, payload: dict[str, Any], ev: list[Evidence]) -> ClaimDraft:
    return ClaimDraft(kind=kind, payload=payload, evidence_ids=tuple(e.id for e in ev), extractor_model=EXTRACTOR_ID)


class RuleExtractor:
    name = "rule"

    def draft(self, evidence: list[Evidence], ledger: list[Evidence] | None = None) -> list[ClaimDraft]:
        """Drafts from ``evidence`` (the new entries); ``ledger`` (all entries so far) supplies cross-references."""
        out: list[ClaimDraft] = []
        everything = list(ledger or evidence)
        hist = next((e for e in everything if e.source in ("alerce", "fink") and e.parsed.get("first_known_detection_mjd") is not None),
                    None)
        for e in evidence:
            p = e.parsed
            if e.source == "fink" and p.get("tns_label"):
                out.append(_draft("prior_classification", {"tns_class": p["tns_label"], "date_kind": "evidence_by",
                                                           "date_mjd": p["first_alert_mjd_with_label"]}, [e]))
            elif e.source == "fink" and p.get("alert_hist_start_mjd") is not None and p.get("first_known_detection_mjd") is not None:
                gap = float(p["first_known_detection_mjd"]) - float(p["alert_hist_start_mjd"])
                if gap >= PRIOR_FLARE_GAP_DAYS:
                    out.append(_draft("prior_flares", {"earlier_activity_mjd": p["alert_hist_start_mjd"],
                                                       "first_known_detection_mjd": p["first_known_detection_mjd"],
                                                       "gap_days": round(gap, 4), "basis": "alert_hist_start"}, [e]))
            elif e.source == "tns" and p.get("report_type") == "classification" and p.get("tns_class"):
                out.append(_draft("prior_classification", {"tns_class": p["tns_class"], "date_kind": "report_date",
                                                           "date_mjd": p["date_mjd"], "tns_name": p["tns_name"]}, [e]))
            elif e.source == "tns" and p.get("report_type") == "discovery" and hist is not None:
                first = float(hist.parsed["first_known_detection_mjd"])
                gap = first - float(p["date_mjd"])
                if gap >= PRIOR_TNS_GAP_DAYS:
                    out.append(_draft("prior_flares", {"earlier_activity_mjd": p["date_mjd"], "first_known_detection_mjd": first,
                                                       "gap_days": round(gap, 4), "basis": "tns_discovery", "ref": p["tns_name"]},
                                      [e, hist]))
            elif e.source == "sherlock" and p.get("ra") is not None and p.get("sep_arcsec") is not None:
                out.extend(self._sherlock(e))
            elif e.source == "simbad":
                out.extend(self._simbad(e))
            elif e.source == "tool" and p.get("quantity"):
                out.append(_draft("analysis_result", {"quantity": p["quantity"], "value": p["value"], "unit": p["unit"]}, [e]))
        return out

    def _sherlock(self, e: Evidence) -> list[ClaimDraft]:
        p = e.parsed
        cls, sep = str(p.get("classification") or ""), float(p["sep_arcsec"])
        src = {"source_id": p["catalogue_object_id"], "source_type": cls, "ra": p["ra"], "dec": p["dec"], "sep_arcsec": sep,
               "catalog": p["catalogue"]}
        out = []
        if cls == "AGN":
            out.append(_draft("known_agn", src, [e]))
        elif cls in SHERLOCK_STAR:
            out.append(_draft("star_counterpart", src, [e]))
        elif cls == "NT" or (p.get("catalogue_object_type") == "galaxy" and sep < NUCLEAR_RADIUS):
            out.append(_draft("nuclear", src, [e]))
        if p.get("catalogue_object_type") == "galaxy" and sep <= HOST_RADIUS:
            z, kind = (p["z"], "spec") if p.get("z") is not None else (p.get("photo_z"), "photo")
            if z is not None:
                out.append(_draft("host_redshift", {"z": z, "z_kind": kind, "host_id": p["catalogue_object_id"], "host_ra": p["ra"],
                                                    "host_dec": p["dec"], "sep_arcsec": sep, "catalog": p["catalogue"]}, [e]))
        return out

    def _simbad(self, e: Evidence) -> list[ClaimDraft]:
        p = e.parsed
        otype, sep = str(p["otype"]), float(p["sep_arcsec"])
        src = {"source_id": p["main_id"], "source_type": otype, "ra": p["ra"], "dec": p["dec"], "sep_arcsec": sep, "catalog": "SIMBAD"}
        if otype in AGN_TYPES and sep <= COUNTERPART_RADIUS:
            return [_draft("known_agn", src, [e])]
        if otype in STAR_TYPES and sep <= COUNTERPART_RADIUS:
            return [_draft("star_counterpart", src, [e])]
        if otype.startswith("G") and sep < NUCLEAR_RADIUS:
            return [_draft("nuclear", src, [e])]
        if p.get("redshift") is not None and sep <= HOST_RADIUS and not otype.endswith("*"):
            return [_draft("host_redshift", {"z": p["redshift"], "z_kind": "spec", "host_id": p["main_id"], "host_ra": p["ra"],
                                             "host_dec": p["dec"], "sep_arcsec": sep, "catalog": "SIMBAD"}, [e])]
        return []
