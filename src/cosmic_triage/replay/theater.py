"""Night Theater S0 artifacts (ARCHITECTURE §8.2): precomputed NightFrames at 5-minute cadence for one night.

The Theater is a player: every position here comes from astropy in Python; the frontend only interpolates.
S0 content: horizon, Sun/Moon, twilight, forward-pool candidates with altitude tracks. No facility activity
(S1) and no Investigator events (S2) are produced yet; the facility state is a constant, labelled idle (L1).
"""

from __future__ import annotations

import numpy as np

from cosmic_triage.contracts import FacilityState, FrameCandidate, MoonState, NightFrame, Snapshot, TheaterNight
from cosmic_triage.contracts.base import RunMode
from cosmic_triage.schedule.visibility import Site, altaz_grid, night_edges, sun_moon_track, twilight_label

CADENCE_MIN = 5.0
PAD_MIN = 30.0


def build_night(
    snapshot: Snapshot, site: Site, run_id: str, mode: RunMode, config_hash: str,
    min_altitude_deg: float | None = None, site_timezone: str | None = None,
) -> tuple[TheaterNight, list[NightFrame]]:
    edges = night_edges(site, snapshot.t_mjd)
    step = CADENCE_MIN / 1440.0
    start = np.floor((edges.sunset - PAD_MIN / 1440.0) / step) * step
    end = np.ceil((edges.sunrise + PAD_MIN / 1440.0) / step) * step
    times = np.round(np.arange(start, end + step / 2, step), 8)
    sm = sun_moon_track(site, times)
    cands = snapshot.candidates
    alt, az = altaz_grid(
        site, np.array([c.context.ra for c in cands]), np.array([c.context.dec for c in cands]), times
    )
    frames = []
    for j, t in enumerate(times):
        frames.append(NightFrame(
            t_mjd=float(t), sun_alt=round(float(sm["sun_alt"][j]), 3), sun_az=round(float(sm["sun_az"][j]), 3),
            moon=MoonState(alt=round(float(sm["moon_alt"][j]), 3), az=round(float(sm["moon_az"][j]), 3),
                           phase=round(float(sm["moon_phase"][j]), 4)),
            twilight=twilight_label(float(sm["sun_alt"][j])),
            candidates=tuple(
                FrameCandidate(oid=c.oid, alt=round(float(alt[i, j]), 3), az=round(float(az[i, j]), 3),
                               belief_top=None, expected_reward=None, is_real_detection_now=False)
                for i, c in enumerate(cands)
            ),
            facility=FacilityState(pointing_oid=None, state="idle", sim_level="L1"),
            events=(),
        ))
    header = TheaterNight(
        run_id=run_id, night_id=snapshot.night_id, mode=mode, config_hash=config_hash, site_name=site.name,
        site_lat=site.lat_deg, site_lon=site.lon_deg, site_height_m=site.height_m, start_mjd=float(times[0]),
        end_mjd=float(times[-1]), cadence_min=CADENCE_MIN, n_frames=len(frames), n_candidates=len(cands),
        sunset_mjd=round(edges.sunset, 6), sunrise_mjd=round(edges.sunrise, 6),
        astro_dusk_mjd=round(edges.astro_dusk, 6), astro_dawn_mjd=round(edges.astro_dawn, 6),
        min_altitude_deg=min_altitude_deg, site_timezone=site_timezone,
    )
    return header, frames
