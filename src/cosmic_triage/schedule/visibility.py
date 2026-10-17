"""Site geometry with astropy (ARCHITECTURE §3.2 `schedule`; §8.2 rule 1: positions are computed in Python).

Consumes only coordinates and times (from a Snapshot); never imports ingest or replay (§13.2).
"""

from __future__ import annotations

from dataclasses import dataclass

import astropy.units as u
import numpy as np
from astroplan import moon_illumination
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body, get_sun
from astropy.time import Time
from astropy.utils import iers

from cosmic_triage.contracts.theater import Twilight

# Determinism + no hidden network: never auto-download IERS tables (sub-arcsecond effect on alt/az).
iers.conf.auto_download = False
iers.conf.auto_max_age = None


@dataclass(frozen=True)
class Site:
    name: str
    lat_deg: float
    lon_deg: float
    height_m: float

    @property
    def location(self) -> EarthLocation:
        return EarthLocation(lat=self.lat_deg * u.deg, lon=self.lon_deg * u.deg, height=self.height_m * u.m)

    @classmethod
    def from_facility(cls, cfg: dict[str, object]) -> Site:
        s = cfg["site"]
        assert isinstance(s, dict)
        return cls(str(s["name"]), float(s["lat_deg"]), float(s["lon_deg"]), float(s["height_m"]))


def twilight_label(sun_alt: float) -> Twilight:
    if sun_alt > -0.833:
        return "day"
    if sun_alt > -6.0:
        return "civil"
    if sun_alt > -12.0:
        return "nautical"
    if sun_alt > -18.0:
        return "astro"
    return "night"


@dataclass(frozen=True)
class NightEdges:
    sunset: float
    sunrise: float
    astro_dusk: float
    astro_dawn: float


def _crossing(times: np.ndarray, alt: np.ndarray, level: float, rising: bool) -> float:
    s = alt - level
    idx = np.where((s[:-1] < 0) & (s[1:] >= 0))[0] if rising else np.where((s[:-1] >= 0) & (s[1:] < 0))[0]
    if len(idx) == 0:
        raise ValueError(f"no {'rising' if rising else 'setting'} crossing of {level} deg")
    i = int(idx[0])
    f = s[i] / (s[i] - s[i + 1])
    return float(times[i] + f * (times[i + 1] - times[i]))


def night_edges(site: Site, t_start_mjd: float) -> NightEdges:
    """Sunset/sunrise and astronomical twilight for the first night after ``t_start_mjd`` (1-minute grid)."""
    grid = t_start_mjd + np.arange(0, 1.0, 1.0 / 1440.0)
    tm = Time(grid, format="mjd", scale="utc")
    alt = get_sun(tm).transform_to(AltAz(obstime=tm, location=site.location)).alt.deg
    sunset = _crossing(grid, alt, -0.833, rising=False)
    dusk = _crossing(grid, alt, -18.0, rising=False)
    after = grid > dusk
    dawn = _crossing(grid[after], alt[after], -18.0, rising=True)
    sunrise = _crossing(grid[after], alt[after], -0.833, rising=True)
    return NightEdges(sunset, sunrise, dusk, dawn)


def sun_moon_track(site: Site, times_mjd: np.ndarray) -> dict[str, np.ndarray]:
    tm = Time(times_mjd, format="mjd", scale="utc")
    frame = AltAz(obstime=tm, location=site.location)
    sun = get_sun(tm).transform_to(frame)
    moon = get_body("moon", tm, location=site.location).transform_to(frame)
    return {
        "sun_alt": sun.alt.deg, "sun_az": sun.az.deg, "moon_alt": moon.alt.deg, "moon_az": moon.az.deg,
        "moon_phase": np.asarray(moon_illumination(tm), dtype=float),
    }


def altaz_grid(site: Site, ra_deg: np.ndarray, dec_deg: np.ndarray, times_mjd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Alt/az for every (target, time): arrays of shape (n_targets, n_times)."""
    if len(ra_deg) == 0:
        return np.zeros((0, len(times_mjd))), np.zeros((0, len(times_mjd)))
    tm = Time(times_mjd, format="mjd", scale="utc")
    coords = SkyCoord(ra=ra_deg[:, None] * u.deg, dec=dec_deg[:, None] * u.deg)
    aa = coords.transform_to(AltAz(obstime=tm[None, :], location=site.location))
    return aa.alt.deg, aa.az.deg
