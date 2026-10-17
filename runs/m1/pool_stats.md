# M1 forward-pool statistics and budget-binding check

Nights: 2025-04-19, 2025-04-20, 2025-04-21, 2025-04-22, 2025-04-23 (decision time t = local date 20:00 UTC). Pre-filter `9f64125e3daf437c` (configs/replay/prefilter.yaml v1.0); BTS snapshot 2026-10-18. All pool counts use data <= t only. Labels use BTS truth (replay-only) and are shown as composition, never fed to any decision.

| Night | Window superset | Pool (pre-filter at t) | Bright (≤ 18.5 at t) | Bright SN-like | class | unknown | contaminant | unscored | BTS saved by t: in pool / in superset |
|---|---|---|---|---|---|---|---|---|---|
| 2025-04-19 | 2785 | 95 | 59 | 59 | 25 | 18 | 36 | 16 | 42 / 53 |
| 2025-04-20 | 2889 | 104 | 62 | 62 | 25 | 20 | 40 | 19 | 43 / 52 |
| 2025-04-21 | 3032 | 103 | 52 | 52 | 24 | 18 | 39 | 22 | 41 / 51 |
| 2025-04-22 | 3208 | 102 | 51 | 51 | 23 | 16 | 40 | 23 | 39 / 54 |
| 2025-04-23 | 3045 | 102 | 47 | 47 | 21 | 17 | 37 | 27 | 38 / 55 |

## Budget-binding check (§6.3)

Rule: choose the spectra-per-night budget B so that median(bright SN-like candidates) / B ≥ 2; if the sky does not supply enough, shrink B (3–4/night), never inflate the pool. Median bright SN-like = **52**.

| B (spectra/night) | median / B | binds (≥ 2)? |
|---|---|---|
| 2 | 26.00 | yes |
| 3 | 17.33 | yes |
| 4 | 13.00 | yes |
| 5 | 10.40 | yes |
| 6 | 8.67 | yes |
| 7 | 7.43 | yes |
| 8 | 6.50 | yes |
| 9 | 5.78 | yes |
| 10 | 5.20 | yes |

**Largest binding budget: B = 26 spectra/night.** The architecture's floor (3–4/night) is satisfied.
Facility: palomar_sedm (overhead 300 s, min altitude 30.0°, moon sep 30.0°).

## Composition

- **2025-04-19** coarse classes among BTS-classified pool members: {'Ia': 20, 'II': 5}; rejection reasons in superset: {'no_real_alert_le_t': 970, 'too_few_detections': 1045, 'fainter_than_max_mag': 1027, 'star_like_counterpart': 158, 'detections_too_close_in_time': 1546, 'near_bright_star': 324, 'first_detection_before_window': 298, 'galactic_plane': 60}; BTS-saved-by-t objects rejected at t: {'near_bright_star': 1, 'too_few_detections': 1, 'fainter_than_max_mag': 10}
- **2025-04-20** coarse classes among BTS-classified pool members: {'Ia': 23, 'II': 1, 'Ibc': 1}; rejection reasons in superset: {'no_real_alert_le_t': 1035, 'too_few_detections': 1116, 'fainter_than_max_mag': 1092, 'star_like_counterpart': 152, 'detections_too_close_in_time': 1582, 'near_bright_star': 344, 'first_detection_before_window': 95, 'galactic_plane': 60}; BTS-saved-by-t objects rejected at t: {'near_bright_star': 1, 'too_few_detections': 3, 'fainter_than_max_mag': 7}
- **2025-04-21** coarse classes among BTS-classified pool members: {'Ia': 23, 'Ibc': 1}; rejection reasons in superset: {'no_real_alert_le_t': 1117, 'too_few_detections': 1210, 'fainter_than_max_mag': 1171, 'star_like_counterpart': 155, 'first_detection_before_window': 286, 'detections_too_close_in_time': 1639, 'near_bright_star': 378, 'galactic_plane': 57}; BTS-saved-by-t objects rejected at t: {'near_bright_star': 1, 'too_few_detections': 5, 'fainter_than_max_mag': 8, 'no_real_alert_le_t': 1}
- **2025-04-22** coarse classes among BTS-classified pool members: {'Ia': 21, 'Ibc': 2}; rejection reasons in superset: {'no_real_alert_le_t': 1210, 'too_few_detections': 1312, 'fainter_than_max_mag': 1286, 'star_like_counterpart': 170, 'near_bright_star': 418, 'detections_too_close_in_time': 1702, 'first_detection_before_window': 316, 'galactic_plane': 64}; BTS-saved-by-t objects rejected at t: {'fainter_than_max_mag': 14, 'too_few_detections': 4}
- **2025-04-23** coarse classes among BTS-classified pool members: {'Ia': 19, 'other_luminous': 1, 'Ibc': 1}; rejection reasons in superset: {'no_real_alert_le_t': 1170, 'too_few_detections': 1255, 'fainter_than_max_mag': 1244, 'star_like_counterpart': 141, 'near_bright_star': 410, 'detections_too_close_in_time': 1598, 'first_detection_before_window': 487, 'galactic_plane': 58}; BTS-saved-by-t objects rejected at t: {'fainter_than_max_mag': 16, 'too_few_detections': 4}

Definitions: *bright SN-like* = pool member whose brightest qualifying detection at t is ≤ 18.5 mag and whose latest alert-time Fink SIMBAD crossmatch is not a stellar/AGN type (`scripts/m0_killtests.py:SN_LIKE_CDS_EXCLUDE`). *BTS saved by t* = in BTS with savedate ≤ t and first detection (≤ t) inside the 14-day window (recall diagnostic for the time-honest filter).
