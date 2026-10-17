from typing import Literal

from pydantic import Field

from cosmic_triage.contracts.base import Band, Contract, SimLevel


class PhotometryPoint(Contract):
    """One ZTF difference-imaging measurement: a detection or a non-detection (upper limit)."""

    mjd: float
    band: Band
    is_detection: bool
    mag: float | None = Field(default=None, description="PSF magnitude (AB) if a detection")
    mag_err: float | None = None
    limiting_mag: float | None = Field(default=None, description="5-sigma limit (AB) if a non-detection")
    drb: float | None = Field(default=None, description="Deep real/bogus score of the alert, if any")
    isdiffpos: bool | None = None
    candid: str | None = None
    source: Literal["alerce", "fink", "lasair", "synthetic"] = "alerce"
    sim_level: SimLevel = "L0"
    simulated: bool = False
