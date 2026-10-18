"""§6.4 label rules from the BTS snapshot (replay-only): class / unknown / contaminant / unscored."""

from __future__ import annotations

import pytest

from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.replay.labels import ClassMap, label_candidate
from cosmic_triage.replay.pool import RawCandidate

SNAP = "2026-10-18"


@pytest.fixture
def bts(fixture_cache):  # type: ignore[no-untyped-def]
    b = BTSCatalog(fixture_cache)
    b.load(SNAP)
    return b


def raw(oid: str, mags: list[float], drb: float | None = 0.99) -> RawCandidate:
    return RawCandidate(oid, [{"mjd": 60000.0 + i, "magpsf": m, "isdiffpos": "t", "drb": drb, "has_stamp": drb is not None}
                              for i, m in enumerate(mags)], [], [])


def test_saved_classified_is_class_with_coarse_mapping(bts) -> None:  # type: ignore[no-untyped-def]
    lab = label_candidate("ZTF25aaafbbk", None, bts, ClassMap(), 18.5)
    assert lab.label == "class" and lab.coarse_class == "Ia" and lab.saved


def test_saved_unclassified_is_unknown(bts) -> None:  # type: ignore[no-untyped-def]
    df = bts._df
    oid = str(df[~df["classified"]]["ZTFID"].iloc[0])
    lab = label_candidate(oid, None, bts, ClassMap(), 18.5)
    assert lab.label == "unknown" and lab.coarse_class is None


def test_never_saved_bright_is_contaminant(bts) -> None:  # type: ignore[no-untyped-def]
    lab = label_candidate("ZTF25notinbts", raw("ZTF25notinbts", [19.2, 18.3, 18.9]), bts, ClassMap(), 18.5)
    assert lab.label == "contaminant" and lab.bright and not lab.saved


def test_never_saved_faint_is_unscored(bts) -> None:  # type: ignore[no-untyped-def]
    lab = label_candidate("ZTF25notinbts", raw("ZTF25notinbts", [19.2, 18.7]), bts, ClassMap(), 18.5)
    assert lab.label is None and not lab.bright


def test_negative_subtractions_do_not_make_an_object_bright(bts) -> None:  # type: ignore[no-untyped-def]
    r = RawCandidate("ZTF25neg", [{"mjd": 1.0, "magpsf": 17.0, "isdiffpos": "f", "drb": 0.99},
                                  {"mjd": 2.0, "magpsf": 19.0, "isdiffpos": "t", "drb": 0.99}], [], [])
    assert label_candidate("ZTF25neg", r, bts, ClassMap(), 18.5).label is None


def test_history_only_bright_detection_does_not_make_a_contaminant(bts) -> None:  # type: ignore[no-untyped-def]
    """Review-03 §6.4 (a): brightness for never-saved objects uses qualifying detections (drb >= 0.5, positive) only."""
    lab = label_candidate("ZTF25notinbts", raw("ZTF25notinbts", [17.5, 18.0], drb=None), bts, ClassMap(), 18.5)
    assert lab.label is None and not lab.bright


def test_low_drb_bright_detection_does_not_make_a_contaminant(bts) -> None:  # type: ignore[no-untyped-def]
    r = RawCandidate("ZTF25lowdrb", [{"mjd": 1.0, "magpsf": 17.0, "isdiffpos": "t", "drb": 0.2},
                                     {"mjd": 2.0, "magpsf": 18.9, "isdiffpos": "t", "drb": 0.99}], [], [])
    lab = label_candidate("ZTF25lowdrb", r, bts, ClassMap(), 18.5)
    assert lab.label is None and lab.peak_mag == 18.9


def test_class_map_covers_common_types() -> None:
    cm = ClassMap()
    assert cm.coarse("SN Ia-91T") == "Ia" and cm.coarse("SN IIn") == "II" and cm.coarse("SN IIb") == "Ibc"
    assert cm.coarse("TDE") == "other_luminous" and cm.coarse("CV") == "contaminant" and cm.coarse("Other") is None
