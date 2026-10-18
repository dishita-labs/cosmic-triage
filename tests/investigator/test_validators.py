"""Corrupted-claim fixtures (§13.5): wrong coordinates, future dates, unsupported excerpts, ... must be rejected."""

from __future__ import annotations

from typing import Any

import pytest

from cosmic_triage.contracts import ClaimDraft, Evidence
from cosmic_triage.investigator.config import InvestigatorConfig
from cosmic_triage.investigator.tools.base import make_evidence
from cosmic_triage.investigator.tools.calculator import separation_arcsec
from cosmic_triage.investigator.validators.chain import Validator
from cosmic_triage.investigator.validators.support import DeterministicVerifier

from .helpers import DEC, RA, T, candidate

CFG = InvestigatorConfig.load()
V = Validator(CFG.validation, DeterministicVerifier())
CAND = candidate()
HOST_RA, HOST_DEC = RA + 0.0017, DEC - 0.0034
HOST_SEP = separation_arcsec(RA, DEC, HOST_RA, HOST_DEC)
SHERLOCK = make_evidence("sherlock", None, T, {"oid": "x"}, {}, {
    "oid": "x", "classification": "SN", "catalogue": "SDSS/2MASS/PS1", "catalogue_object_id": "1237668332027641933",
    "catalogue_object_type": "galaxy", "ra": HOST_RA, "dec": HOST_DEC, "sep_arcsec": round(HOST_SEP, 2), "z": 0.052,
    "photo_z": 0.041, "photo_z_err": 0.012})
FINK_TNS = make_evidence("fink", T - 2.0, T, {"kind": "tns_label_at_alert_time"}, {},
                         {"oid": "x", "tns_label": "SN Ia", "first_alert_mjd_with_label": T - 2.0, "alert_candid": "222"})
AGN = make_evidence("simbad", None, T, {"main_id": "Q1"}, {}, {"catalog": "SIMBAD", "main_id": "Q1", "otype": "QSO", "ra": RA,
                                                               "dec": DEC + 0.0001, "sep_arcsec": 0.36, "redshift": None,
                                                               "redshift_bibcode": None})


def host_draft(**over: Any) -> ClaimDraft:
    payload = {"z": 0.052, "z_kind": "spec", "host_id": "1237668332027641933", "host_ra": HOST_RA, "host_dec": HOST_DEC,
               "sep_arcsec": round(HOST_SEP, 2), "catalog": "SDSS/2MASS/PS1", **over.pop("payload", {})}
    return ClaimDraft(kind=over.pop("kind", "host_redshift"), payload=payload, evidence_ids=over.pop("ids", (SHERLOCK.id,)),
                      extractor_model="test")


def run(draft: ClaimDraft, *evs: Evidence) -> tuple[bool, set[str]]:
    rep, _ = V.validate(draft, {e.id: e for e in (evs or (SHERLOCK,))}, T, CAND, "run")
    return rep.accepted, {c.name for c in rep.checks if not c.passed}


def test_valid_host_redshift_is_accepted() -> None:
    assert run(host_draft()) == (True, set())


def test_valid_evidence_by_classification_is_accepted() -> None:
    d = ClaimDraft(kind="prior_classification", payload={"tns_class": "SN Ia", "date_kind": "evidence_by", "date_mjd": T - 2.0},
                   evidence_ids=(FINK_TNS.id,), extractor_model="test")
    assert run(d, FINK_TNS) == (True, set())


@pytest.mark.parametrize("name, draft, evs, failing", [
    ("wrong host coordinates", host_draft(payload={"host_ra": HOST_RA + 0.01}), None, {"geometry", "support"}),
    ("claimed separation inconsistent with coordinates", host_draft(payload={"sep_arcsec": 2.0}), None, {"geometry"}),
    ("redshift not in the excerpt", host_draft(payload={"z": 0.061}), None, {"type_specific", "support"}),
    ("redshift out of range", host_draft(payload={"z": 3.5}), None, {"type_specific", "support"}),
    ("cites evidence not in the ledger", host_draft(ids=("ev-sherlock-doesnotexist",)), None, {"provenance", "support"}),
    ("cites nothing", host_draft(ids=()), None, {"provenance", "support"}),
    ("schema violation", host_draft(payload={"z_kind": "guess"}), None, {"schema", "geometry", "type_specific"}),
])
def test_corrupted_host_claims_are_rejected(name: str, draft: ClaimDraft, evs: Any, failing: set[str]) -> None:
    ok, failed = run(draft)
    assert not ok, name
    assert failing <= failed, (name, failed)


def test_future_dated_evidence_is_rejected_by_date_le_t() -> None:
    future = make_evidence("fink", T + 1.0, T, {"kind": "tns_label_at_alert_time"}, {},
                           {"oid": "x", "tns_label": "SN Ia", "first_alert_mjd_with_label": T + 1.0, "alert_candid": "333"})
    d = ClaimDraft(kind="prior_classification", payload={"tns_class": "SN Ia", "date_kind": "evidence_by", "date_mjd": T + 1.0},
                   evidence_ids=(future.id,), extractor_model="test")
    ok, failed = run(d, future)
    assert not ok and "date_le_t" in failed


def test_evidence_retrieved_at_another_t_is_rejected() -> None:
    other = make_evidence("sherlock", None, T + 5.0, {"oid": "x"}, {}, dict(SHERLOCK.parsed))
    ok, failed = run(host_draft(ids=(other.id,)), other)
    assert not ok and "date_le_t" in failed


def test_evidence_by_must_cite_fink_not_a_report() -> None:
    d = ClaimDraft(kind="prior_classification", payload={"tns_class": "SN Ia", "date_kind": "evidence_by", "date_mjd": T - 2.0},
                   evidence_ids=(SHERLOCK.id,), extractor_model="test")
    ok, failed = run(d)
    assert not ok and "type_specific" in failed


def test_report_date_requires_a_tns_classification_report() -> None:
    """Review-03: report_date comes only from a TNS classification report; a Fink label cannot be relabelled as one."""
    d = ClaimDraft(kind="prior_classification", payload={"tns_class": "SN Ia", "date_kind": "report_date", "date_mjd": T - 2.0},
                   evidence_ids=(FINK_TNS.id,), extractor_model="test")
    ok, failed = run(d, FINK_TNS)
    assert not ok and "type_specific" in failed


def test_unsupported_class_in_excerpt_is_rejected() -> None:
    d = ClaimDraft(kind="prior_classification", payload={"tns_class": "SN II", "date_kind": "evidence_by", "date_mjd": T - 2.0},
                   evidence_ids=(FINK_TNS.id,), extractor_model="test")
    ok, failed = run(d, FINK_TNS)
    assert not ok and {"type_specific", "support"} <= failed


def test_agn_counterpart_outside_radius_is_rejected() -> None:
    far = make_evidence("simbad", None, T, {"main_id": "Q2"}, {}, {**AGN.parsed, "main_id": "Q2", "dec": DEC + 0.001, "sep_arcsec": 3.6})
    d = ClaimDraft(kind="known_agn", payload={"source_id": "Q2", "source_type": "QSO", "ra": RA, "dec": DEC + 0.001, "sep_arcsec": 3.6,
                                              "catalog": "SIMBAD"}, evidence_ids=(far.id,), extractor_model="test")
    ok, failed = run(d, far)
    assert not ok and "geometry" in failed


def test_agn_counterpart_within_radius_is_accepted() -> None:
    d = ClaimDraft(kind="known_agn", payload={"source_id": "Q1", "source_type": "QSO", "ra": RA, "dec": DEC + 0.0001, "sep_arcsec": 0.36,
                                              "catalog": "SIMBAD"}, evidence_ids=(AGN.id,), extractor_model="test")
    assert run(d, AGN) == (True, set())


def test_star_claim_citing_a_galaxy_is_rejected() -> None:
    d = ClaimDraft(kind="star_counterpart", payload={"source_id": "1237668332027641933", "source_type": "SN", "ra": HOST_RA,
                                                     "dec": HOST_DEC, "sep_arcsec": round(HOST_SEP, 2), "catalog": "SDSS/2MASS/PS1"},
                   evidence_ids=(SHERLOCK.id,), extractor_model="test")
    ok, failed = run(d)
    assert not ok and "type_specific" in failed


TNS_OLD = make_evidence("tns", T - 1888.3, T, {"via": "lasair.crossmatch_tns"}, {},
                        {"report_type": "discovery", "via": "lasair.crossmatch_tns", "tns_name": "2020dig", "date_mjd": T - 1888.3,
                         "ra": RA, "dec": DEC, "disc_mag": 18.9, "disc_mag_filter": "g", "source_group": "ZTF"})
HIST = make_evidence("fink", T - 2.0, T, {"kind": "alert_fields"}, {},
                     {"oid": "x", "alert_hist_start_mjd": T - 5.0, "alert_ndethist": 2, "first_known_detection_mjd": T - 5.0,
                      "latest_snn_snia_vs_nonia": 0.6, "latest_snn_sn_vs_all": 0.7, "latest_cdsxmatch": "Unknown"})


def flares(**over: Any) -> ClaimDraft:
    payload = {"earlier_activity_mjd": T - 1888.3, "first_known_detection_mjd": T - 5.0, "gap_days": round(1883.3, 4),
               "basis": "tns_discovery", "ref": "2020dig", **over}
    return ClaimDraft(kind="prior_flares", payload=payload, evidence_ids=(TNS_OLD.id, HIST.id), extractor_model="test")


def test_prior_flares_from_an_earlier_tns_discovery_is_accepted() -> None:
    assert run(flares(), TNS_OLD, HIST) == (True, set())


def test_prior_flares_with_a_wrong_gap_or_ref_is_rejected() -> None:
    assert not run(flares(gap_days=10.0), TNS_OLD, HIST)[0]
    ok, failed = run(flares(ref="2020xyz"), TNS_OLD, HIST)
    assert not ok and "type_specific" in failed


def test_zero_redshift_placeholder_is_rejected() -> None:
    """Hand-review finding (M2): Lasair encodes 'no redshift' as 0.0; a z = 0 host claim must never be accepted."""
    zero = make_evidence("sherlock", None, T, {"oid": "y"}, {}, {**SHERLOCK.parsed, "oid": "y", "z": 0.0})
    ok, failed = run(host_draft(payload={"z": 0.0}, ids=(zero.id,)), zero)
    assert not ok and "type_specific" in failed
