"""Units used throughout Cosmic Triage (§13.2). Every contract field follows these conventions.

- Time: Modified Julian Date (MJD, days). ``MJD = JD - 2400000.5``.
- Brightness: AB magnitudes. Smaller is brighter. Upper limits are 5-sigma limiting magnitudes.
- Separations: arcseconds.
- Sky coordinates: degrees (ICRS RA/Dec; Galactic latitude ``b`` in degrees).
- Durations: seconds (exposure, overhead, slew).
- Money: US dollars.
"""

from typing import Final

JD_MJD_OFFSET: Final[float] = 2400000.5
# The BTS Sample Explorer reports ``peakt`` as JD - 2458000.
BTS_PEAKT_JD_OFFSET: Final[float] = 2458000.0
SECONDS_PER_DAY: Final[float] = 86400.0


def jd_to_mjd(jd: float) -> float:
    return jd - JD_MJD_OFFSET


def mjd_to_jd(mjd: float) -> float:
    return mjd + JD_MJD_OFFSET


def bts_peakt_to_mjd(peakt: float) -> float:
    return jd_to_mjd(peakt + BTS_PEAKT_JD_OFFSET)
