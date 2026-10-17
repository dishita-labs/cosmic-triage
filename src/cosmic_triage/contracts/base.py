"""Shared base model and literal types for all contracts."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

JsonValue = Any  # JSON-serialisable payloads (dict/list/str/float/int/bool/None)

ClassK = Literal["Ia", "II", "Ibc", "other_luminous", "contaminant"]
CLASSES_K: tuple[ClassK, ...] = ("Ia", "II", "Ibc", "other_luminous", "contaminant")

Label = Literal["class", "unknown", "contaminant"]
SimLevel = Literal["L0", "L1", "L2", "L3"]
RunMode = Literal["exploratory", "bench"]
Band = Literal["g", "r", "i"]


class Contract(BaseModel):
    """Strict, immutable, NaN-free base for every contract.

    ``extra="forbid"`` makes the field list a type-level boundary: a denylisted field
    (``type``, ``redshift``, ``peak*``, ...) cannot ride along on a Snapshot.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
