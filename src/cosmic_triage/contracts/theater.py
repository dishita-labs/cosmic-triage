"""Night Theater player data (§8.2, §13.3). Computed in Python with astropy; the frontend only interpolates."""

from typing import Literal

from cosmic_triage.contracts.base import Contract, SimLevel

Twilight = Literal["day", "civil", "nautical", "astro", "night"]


class MoonState(Contract):
    alt: float
    az: float
    phase: float  # illuminated fraction, 0..1


class FrameCandidate(Contract):
    oid: str
    alt: float
    az: float
    belief_top: str | None = None
    expected_reward: float | None = None
    is_real_detection_now: bool = False


class FacilityState(Contract):
    pointing_oid: str | None = None
    state: Literal["idle", "slewing", "exposing", "down"] = "idle"
    sim_level: Literal["L1"] = "L1"


class TheaterEvent(Contract):
    t_mjd: float
    kind: Literal["detection", "report", "gate", "tool", "claim", "schedule", "outcome"]
    ref_id: str
    oid: str | None = None
    sim_level: SimLevel
    label: str = ""


class NightFrame(Contract):
    t_mjd: float
    sun_alt: float
    sun_az: float
    moon: MoonState
    twilight: Twilight
    candidates: tuple[FrameCandidate, ...]
    facility: FacilityState
    events: tuple[TheaterEvent, ...] = ()


class TheaterNight(Contract):
    """Header for one precomputed night: site, run provenance and the frame cadence."""

    run_id: str
    night_id: str
    mode: Literal["exploratory", "bench"]
    config_hash: str
    site_name: str
    site_lat: float
    site_lon: float
    site_height_m: float
    start_mjd: float
    end_mjd: float
    cadence_min: float
    n_frames: int
    n_candidates: int
    sunset_mjd: float
    sunrise_mjd: float
    astro_dusk_mjd: float
    astro_dawn_mjd: float
    min_altitude_deg: float | None = None  # facility altitude limit (from config), drawn as a ring
    site_timezone: str | None = None  # IANA zone for local-time labels (presentation only)
