"""M0 completion criterion: every contract round-trips JSON via model_validate(model_dump())."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cosmic_triage import contracts as C
from tests.contracts.examples import EXAMPLES

SNAPSHOT = Path(__file__).parent / "schema_snapshot.json"


def test_every_contract_has_an_example() -> None:
    assert set(C.ALL_CONTRACTS) == set(EXAMPLES), set(C.ALL_CONTRACTS) ^ set(EXAMPLES)


@pytest.mark.parametrize("cls", C.ALL_CONTRACTS, ids=lambda c: c.__name__)
def test_roundtrip_python(cls: type[C.Contract]) -> None:
    obj = EXAMPLES[cls]
    assert cls.model_validate(obj.model_dump()) == obj  # type: ignore[attr-defined]


@pytest.mark.parametrize("cls", C.ALL_CONTRACTS, ids=lambda c: c.__name__)
def test_roundtrip_json(cls: type[C.Contract]) -> None:
    obj = EXAMPLES[cls]
    js = obj.model_dump_json()  # type: ignore[attr-defined]
    assert cls.model_validate_json(js) == obj
    assert cls.model_validate(json.loads(js)) == obj


@pytest.mark.parametrize("cls", C.ALL_CONTRACTS, ids=lambda c: c.__name__)
def test_extra_fields_forbidden(cls: type[C.Contract]) -> None:
    data = EXAMPLES[cls].model_dump()  # type: ignore[attr-defined]
    data["type"] = "SN Ia"  # a denylisted field must not be able to ride along
    with pytest.raises(ValidationError):
        cls.model_validate(data)


def test_nan_rejected() -> None:
    with pytest.raises(ValidationError):
        C.PhotometryPoint(mjd=float("nan"), band="r", is_detection=True, mag=18.0)


def test_belief_must_be_normalised() -> None:
    with pytest.raises(ValidationError):
        C.Belief(oid="x", t_mjd=1.0, probs={"Ia": 0.9, "II": 0.9}, entropy_nats=0.1, config_hash="h")


def test_snapshot_rejects_future_photometry() -> None:
    from tests.contracts.examples import CS, SNAP

    late = CS.photometry[1].model_copy(update={"mjd": SNAP.t_mjd + 0.01})
    bad = CS.model_copy(update={"photometry": (late,)})
    with pytest.raises(ValidationError):
        C.Snapshot.model_validate({**SNAP.model_dump(), "candidates": [bad.model_dump()]})


def current_schema() -> dict[str, object]:
    return {cls.__name__: cls.model_json_schema() for cls in C.ALL_CONTRACTS}


def test_schema_snapshot() -> None:
    """A schema change fails CI until the snapshot is intentionally updated (§13.5):
    `uv run python scripts/update_schema_snapshot.py`."""
    assert SNAPSHOT.exists(), "schema snapshot missing; run scripts/update_schema_snapshot.py"
    assert json.loads(SNAPSHOT.read_text()) == json.loads(json.dumps(current_schema()))
