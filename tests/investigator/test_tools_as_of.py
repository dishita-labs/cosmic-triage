"""As-of filtering at the tool layer (§4.1, §13.5): planted post-t information must never leave a tool."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from cosmic_triage.contracts import Evidence
from cosmic_triage.investigator.tools.base import ToolAsOfViolation, ToolRegistry, ToolResult, make_evidence
from cosmic_triage.investigator.tools.history import AlertHistoryTool, HistoryInput
from cosmic_triage.investigator.tools.reports import ReportInput, ReportLookupTool
from cosmic_triage.investigator.tools.sherlock import SherlockInput, SherlockTool
from cosmic_triage.investigator.tools.simbad import SimbadConeTool, SimbadInput

from .helpers import DEC, RA, FakeLasair, FakeSimbad, FakeTNS, T, candidate

LASAIR_ROW = {"tns_name": "2025hnv", "tns_prefix": "SN", "type": "SN Ia", "z": 0.052, "hostz": 0.0521, "host_name": "SDSS J1437",
              "disc_date": "2025-04-17T22:42:27.360000", "disc_mag": 18.54, "disc_mag_filter": "L", "ra": RA, "decl": DEC,
              "lastmodified_date": "2025-06-15T13:24:45", "lasairmodified_date": "2025-10-23T12:58:27",
              "disc_int_name": "GOTO25bxc, ATLAS25dxf", "source_group": "GOTO", "sender": "GOTO"}


def dump(evs: tuple[Evidence, ...]) -> str:
    return json.dumps([e.model_dump() for e in evs])


def test_lasair_tns_fallback_keeps_only_the_discovery_report() -> None:
    tool = ReportLookupTool(FakeLasair([LASAIR_ROW]), FakeTNS())  # type: ignore[arg-type]
    res = tool.run(ReportInput(oid="ZTF25aankqhe", ra=RA, dec=DEC, radius_arcsec=3.0), T)
    assert res.output.mode == "lasair_fallback"  # type: ignore[attr-defined]
    assert len(res.evidence) == 1 and res.evidence[0].parsed["report_type"] == "discovery"
    text = dump(res.evidence)
    for leaked in ("SN Ia", "0.052", "0.0521", "SDSS J1437", "2025-06-15", "2025-10-23", "ATLAS25dxf", '"SN"'):
        assert leaked not in text, leaked
    assert res.evidence[0].source_date is not None and res.evidence[0].source_date <= T


def test_lasair_tns_discovery_after_t_is_dropped() -> None:
    row = {**LASAIR_ROW, "disc_date": "2025-04-30T01:00:00"}
    res = ReportLookupTool(FakeLasair([row]), FakeTNS()).run(  # type: ignore[arg-type]
        ReportInput(oid="ZTF25aankqhe", ra=RA, dec=DEC, radius_arcsec=3.0), T)
    assert res.evidence == () and res.filtered_post_t == 1


def test_simbad_drops_transient_entries_and_post_t_redshifts() -> None:
    rows = [
        {"main_id": "SN 2025hnv", "otype": "SN", "ra": RA, "dec": DEC, "sep_arcsec": 0.1, "rvz_redshift": 0.052, "rvz_bibcode": "2025TNSCR"},
        {"main_id": "AT 2025abc", "otype": "Transient", "ra": RA, "dec": DEC, "sep_arcsec": 0.2, "rvz_redshift": "", "rvz_bibcode": ""},
        {"main_id": "Gal A", "otype": "G", "ra": RA + 0.003, "dec": DEC, "sep_arcsec": 10.4, "rvz_redshift": 0.05, "rvz_bibcode": "2025ApJ...1..1X"},
        {"main_id": "Gal B", "otype": "G", "ra": RA + 0.001, "dec": DEC, "sep_arcsec": 3.5, "rvz_redshift": 0.031, "rvz_bibcode": "2009ApJS..182..543A"},
    ]
    res = SimbadConeTool(FakeSimbad(rows)).run(SimbadInput(ra=RA, dec=DEC, radius_arcsec=10.0), T)  # type: ignore[arg-type]
    names = [e.parsed["main_id"] for e in res.evidence]
    assert names == ["Gal A", "Gal B"]
    a, b = res.evidence
    assert a.parsed["redshift"] is None and a.source_date is None          # 2025 reference: not provably <= t
    assert b.parsed["redshift"] == 0.031 and b.source_date is not None and b.source_date <= T
    assert "0.052" not in dump(res.evidence)


def test_history_tns_label_is_first_alert_le_t_and_dated_evidence_by() -> None:
    c = candidate(tns={T - 2.0: "SN Ia"})
    res = AlertHistoryTool().run(HistoryInput(candidate=c), T)
    lab = [e for e in res.evidence if e.parsed.get("tns_label")]
    assert len(lab) == 1 and lab[0].source_date == pytest.approx(T - 2.0)
    assert lab[0].parsed["first_alert_mjd_with_label"] == pytest.approx(T - 2.0)


def test_sherlock_drops_free_text_description() -> None:
    row = {"classification": "SN", "association_type": "SN", "catalogue_table_name": "SDSS/2MASS/PS1", "catalogue_object_id": 123,
           "catalogue_object_type": "galaxy", "raDeg": RA, "decDeg": DEC + 0.003, "separationArcsec": 10.8, "z": 0.052,
           "photoZ": 0.041, "photoZErr": 0.01, "description": "A host z=0.052 implies m - M = 36.83"}
    res = SherlockTool(FakeLasair(sherlock_rows=[row])).run(SherlockInput(oid="ZTF25x"), T)  # type: ignore[arg-type]
    assert res.evidence[0].source_date is None and "36.83" not in dump(res.evidence)


class _Rogue:
    name, description, as_of_aware = "rogue", "emits the future", True

    class Input(BaseModel):
        x: int = 0

    Output = Input

    def build_input(self, ctx, ledger):  # type: ignore[no-untyped-def]
        return self.Input()

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult:
        return ToolResult(self.Input(), (make_evidence("tool", t_mjd + 0.01, t_mjd, {}, {}, {"x": 1}),))


def test_registry_rejects_evidence_dated_after_t() -> None:
    reg = ToolRegistry()
    reg.register(_Rogue())  # type: ignore[arg-type]
    with pytest.raises(ToolAsOfViolation):
        reg.run("rogue", _Rogue.Input(), T)


def test_sherlock_zero_placeholders_become_missing() -> None:
    row = {"classification": "SN", "association_type": "SN", "catalogue_table_name": "2MASS/PS1", "catalogue_object_id": 18204668,
           "catalogue_object_type": "galaxy", "raDeg": RA, "decDeg": DEC, "separationArcsec": 13.87, "z": 0.0, "photoZ": 0.0}
    p = SherlockTool(FakeLasair(sherlock_rows=[row])).run(SherlockInput(oid="ZTF25x"), T).evidence[0].parsed  # type: ignore[arg-type]
    assert p["z"] is None and p["photo_z"] is None and p["ra"] == RA
    orphan = {"classification": "ORPHAN", "catalogue_object_id": 0, "catalogue_object_type": 0, "raDeg": 0.0, "decDeg": 0.0,
              "separationArcsec": 0.0, "z": 0.0, "photoZ": 0.0}
    p = SherlockTool(FakeLasair(sherlock_rows=[orphan])).run(SherlockInput(oid="ZTF25y"), T).evidence[0].parsed  # type: ignore[arg-type]
    assert p["ra"] is None and p["sep_arcsec"] is None and p["catalogue_object_id"] is None
