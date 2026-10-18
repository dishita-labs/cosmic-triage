"""Cutout triplet (science/template/difference) of the first real alert <= t, from ALeRCE. Hashes only in M2;
image reading is M7 (§4.1 #6)."""

from __future__ import annotations

from pydantic import BaseModel

from cosmic_triage.contracts.base import Contract
from cosmic_triage.ingest import AlerceClient
from cosmic_triage.ingest.errors import ExternalAPIError, NetworkDisabled, OfflineCacheMiss
from cosmic_triage.investigator.tools.base import (
    LedgerView,
    ToolContext,
    ToolResult,
    ToolUnavailable,
    ToolUpstreamError,
    make_evidence,
)
from cosmic_triage.settings import sha256_hex

KINDS = ("science", "template", "difference")


class CutoutInput(Contract):
    oid: str
    candid: str
    alert_mjd: float


class CutoutOutput(Contract):
    candid: str
    alert_mjd: float
    sha256: dict[str, str]
    n_bytes: dict[str, int]


class CutoutTool:
    name = "cutouts"
    description = "Fetch the cutout triplet of the first real alert known at t (hashed; read by M7 vision)."
    Input = CutoutInput
    Output = CutoutOutput
    as_of_aware = True

    def __init__(self, alerce: AlerceClient) -> None:
        self.alerce = alerce

    def build_input(self, ctx: ToolContext, ledger: LedgerView) -> BaseModel | None:
        alerts = sorted((p for p in ctx.candidate.photometry if p.is_detection and p.drb is not None and p.candid
                         and p.mjd <= ctx.t_mjd), key=lambda p: p.mjd)
        if not alerts:
            return None
        a = alerts[0]
        assert a.candid is not None
        return CutoutInput(oid=ctx.candidate.oid, candid=a.candid, alert_mjd=a.mjd)

    def run(self, inp: BaseModel, t_mjd: float) -> ToolResult:
        assert isinstance(inp, CutoutInput)
        if inp.alert_mjd > t_mjd:
            raise ToolUnavailable("alert after t")
        try:
            imgs = {k: self.alerce.stamp(inp.oid, inp.candid, k) for k in KINDS}
        except (OfflineCacheMiss, NetworkDisabled) as exc:
            raise ToolUnavailable(str(exc)) from None
        except ExternalAPIError as exc:
            raise ToolUpstreamError(str(exc)) from None
        out = CutoutOutput(candid=inp.candid, alert_mjd=inp.alert_mjd, sha256={k: sha256_hex(v) for k, v in imgs.items()},
                           n_bytes={k: len(v) for k, v in imgs.items()})
        parsed = {"oid": inp.oid, "candid": inp.candid, "alert_mjd": inp.alert_mjd, "sha256": out.sha256, "format": "png"}
        return ToolResult(out, (make_evidence("cutout", inp.alert_mjd, t_mjd, {"oid": inp.oid, "candid": inp.candid},
                                              out.sha256, parsed),))
