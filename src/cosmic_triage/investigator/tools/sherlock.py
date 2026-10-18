"""Sherlock host/context (Lasair): static-catalog association. ``source_date`` is None (static context).

Only structured catalogue fields are kept; the free-text ``description`` (which embeds derived distances) is dropped.
Lasair encodes missing values as 0 (``z``, ``photoZ``, and the coordinates/type of an ORPHAN with no association);
those placeholders are mapped to None so a 0.0 can never be read as a measurement.
Caveat recorded in the M2 report: Sherlock's catalogue redshifts are treated as static, which assumes the catalogues
predate t.
"""

from __future__ import annotations

from pydantic import BaseModel

from cosmic_triage.contracts.base import Contract
from cosmic_triage.ingest import LasairClient
from cosmic_triage.ingest.errors import CredentialMissing, ExternalAPIError, OfflineCacheMiss
from cosmic_triage.investigator.tools.base import (
    LedgerView,
    ToolContext,
    ToolResult,
    ToolUnavailable,
    ToolUpstreamError,
    make_evidence,
)

KEEP = ("classification", "association_type", "catalogue_table_name", "catalogue_object_id", "catalogue_object_type",
        "raDeg", "decDeg", "separationArcsec", "z", "photoZ", "photoZErr", "major_axis_arcsec", "Mag", "MagFilter")


class SherlockInput(Contract):
    oid: str


class SherlockOutput(Contract):
    classification: str | None
    catalogue_object_type: str | None
    separation_arcsec: float | None
    z: float | None
    photo_z: float | None


def _num(x: object) -> float | None:
    try:
        return None if x is None else float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _nz(x: object) -> float | None:
    """Lasair placeholder: 0 means 'no value' for redshifts."""
    v = _num(x)
    return None if v is None or v == 0.0 else v


class SherlockTool:
    name = "sherlock"
    description = "Lasair Sherlock association of the position with static catalogues (host, AGN, star, nuclear)."
    Input = SherlockInput
    Output = SherlockOutput
    as_of_aware = True

    def __init__(self, lasair: LasairClient) -> None:
        self.lasair = lasair

    def build_input(self, ctx: ToolContext, ledger: LedgerView) -> BaseModel | None:
        return SherlockInput(oid=ctx.candidate.oid)

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult:
        assert isinstance(inp, SherlockInput)
        try:
            rows = self.lasair.sherlock_object(inp.oid)
        except (CredentialMissing, OfflineCacheMiss) as exc:
            raise ToolUnavailable(str(exc)) from None
        except ExternalAPIError as exc:
            raise ToolUpstreamError(str(exc)) from None
        if not rows:
            return ToolResult(SherlockOutput(classification=None, catalogue_object_type=None, separation_arcsec=None,
                                             z=None, photo_z=None), ())
        r = rows[0]
        kept = {k: r.get(k) for k in KEEP}
        associated = str(kept["catalogue_object_id"] or "0") not in ("0", "", "None") and kept["classification"] != "ORPHAN"
        parsed = {"oid": inp.oid, "classification": kept["classification"], "association_type": kept["association_type"],
                  "catalogue": kept["catalogue_table_name"] if associated else None,
                  "catalogue_object_id": str(kept["catalogue_object_id"]) if associated else None,
                  "catalogue_object_type": kept["catalogue_object_type"] if associated else None,
                  "ra": _num(kept["raDeg"]) if associated else None, "dec": _num(kept["decDeg"]) if associated else None,
                  "sep_arcsec": _num(kept["separationArcsec"]) if associated else None, "z": _nz(kept["z"]),
                  "photo_z": _nz(kept["photoZ"]), "photo_z_err": _nz(kept["photoZErr"]) if _nz(kept["photoZ"]) else None}
        out = SherlockOutput(classification=parsed["classification"], catalogue_object_type=parsed["catalogue_object_type"],
                             separation_arcsec=parsed["sep_arcsec"], z=parsed["z"], photo_z=parsed["photo_z"])
        return ToolResult(out, (make_evidence("sherlock", None, t_mjd, {"oid": inp.oid}, kept, parsed),))
