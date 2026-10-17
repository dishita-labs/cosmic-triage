from pydantic import Field

from cosmic_triage.contracts.base import Contract
from cosmic_triage.contracts.photometry import PhotometryPoint


class CandidateContext(Contract):
    """Static (time-independent) context of a candidate's position."""

    ra: float
    dec: float
    gal_b: float = Field(description="Galactic latitude, degrees")
    sgscore1: float | None = Field(default=None, description="PS1 star/galaxy score of nearest source")
    distpsnr1: float | None = Field(default=None, description="Distance to nearest PS1 source, arcsec")
    srmag1: float | None = Field(default=None, description="r mag of nearest PS1 source")
    neargaia: float | None = Field(default=None, description="Distance to nearest Gaia source, arcsec")
    maggaia: float | None = Field(default=None, description="G mag of nearest Gaia source")


class FinkAlertRow(Contract):
    """Alert-time Fink scores for one detection (replay-safe photometry channel, §6.1)."""

    mjd: float
    candid: str | None = None
    rf_snia_vs_nonia: float | None = None
    snn_snia_vs_nonia: float | None = None
    snn_sn_vs_all: float | None = None
    cdsxmatch: str | None = None
    tns_alert_time: str | None = Field(
        default=None, description="Fink's TNS crossmatch label as of this alert (d:tns)"
    )


class StampPrior(Contract):
    """ALeRCE stamp-classifier probabilities from the first alert (time-honest, §6.1)."""

    first_alert_mjd: float
    classifier_version: str
    probs: dict[str, float]


class CandidateState(Contract):
    """Everything known about one candidate at snapshot time t. All counts are recomputed from data <= t."""

    oid: str
    t_mjd: float
    context: CandidateContext
    photometry: tuple[PhotometryPoint, ...]
    fink_rows: tuple[FinkAlertRow, ...] = ()
    stamp_prior: StampPrior | None = None
    first_detection_mjd: float
    last_detection_mjd: float
    n_detections: int = Field(description="Detections with mjd <= t (recomputed, never ndethist-final)")
    n_nondetections: int
    brightest_mag: float
    latest_mag: float
    latest_band: str
