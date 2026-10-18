# Forward-pool statistics and budget-binding check (regenerated in M1.1)

Nights: 2025-04-19, 2025-04-20, 2025-04-21, 2025-04-22, 2025-04-23 (decision time t = local date 20:00 UTC). Pre-filter `9669bcad8c932e03` (configs/replay/prefilter.yaml v1.1); BTS snapshot 2026-10-18. All pool counts use data <= t only. Labels use BTS truth (replay-only) and are shown as composition, never fed to any decision.

| Night | Window superset | Pool (pre-filter at t) | Bright (≤ 18.5 at t) | Bright SN-like | class | unknown | contaminant | unscored | BTS saved by t: in pool / in superset |
|---|---|---|---|---|---|---|---|---|---|
| 2025-04-19 | 2785 | 79 | 52 | 52 | 17 | 12 | 36 | 14 | 29 / 66 |
| 2025-04-20 | 2889 | 90 | 55 | 55 | 20 | 14 | 39 | 17 | 33 / 63 |
| 2025-04-21 | 3032 | 91 | 46 | 46 | 21 | 15 | 36 | 19 | 35 / 51 |
| 2025-04-22 | 3208 | 95 | 51 | 51 | 20 | 13 | 42 | 20 | 33 / 56 |
| 2025-04-23 | 3045 | 99 | 48 | 48 | 20 | 15 | 39 | 25 | 35 / 56 |

## Before / after M1.1 (pre-filter v1.0 → v1.1, never-saved brightness from qualifying detections)

| Night | Pool before → after | Contaminant before → after | Left pool | Joined pool | Labels before | Labels after |
|---|---|---|---|---|---|---|
| 2025-04-19 | 95 → 79 | 36 → 36 | 17 | 1 | {'contaminant': 36, 'class': 25, 'unknown': 18, 'unscored': 16} | {'contaminant': 36, 'unknown': 12, 'class': 17, 'unscored': 14} |
| 2025-04-20 | 104 → 90 | 40 → 39 | 15 | 1 | {'contaminant': 40, 'unscored': 19, 'class': 25, 'unknown': 20} | {'contaminant': 39, 'class': 20, 'unscored': 17, 'unknown': 14} |
| 2025-04-21 | 103 → 91 | 39 → 36 | 13 | 1 | {'contaminant': 39, 'unscored': 22, 'class': 24, 'unknown': 18} | {'contaminant': 36, 'unscored': 19, 'class': 21, 'unknown': 15} |
| 2025-04-22 | 102 → 95 | 40 → 42 | 13 | 6 | {'contaminant': 40, 'unscored': 23, 'class': 23, 'unknown': 16} | {'contaminant': 42, 'class': 20, 'unscored': 20, 'unknown': 13} |
| 2025-04-23 | 102 → 99 | 37 → 39 | 10 | 7 | {'contaminant': 37, 'unscored': 27, 'unknown': 17, 'class': 21} | {'contaminant': 39, 'unscored': 25, 'class': 20, 'unknown': 15} |

## Budget-binding check (§6.3)

Rule: choose the spectra-per-night budget B so that median(bright SN-like candidates) / B ≥ 2; if the sky does not supply enough, shrink B (3–4/night), never inflate the pool. Median bright SN-like = **51**.

| B (spectra/night) | median / B | binds (≥ 2)? |
|---|---|---|
| 2 | 25.50 | yes |
| 3 | 17.00 | yes |
| 4 | 12.75 | yes |
| 5 | 10.20 | yes |
| 6 | 8.50 | yes |
| 7 | 7.29 | yes |
| 8 | 6.38 | yes |
| 9 | 5.67 | yes |
| 10 | 5.10 | yes |

**Largest binding budget: B = 25 spectra/night.** The architecture's floor (3–4/night) is satisfied.
Facility: palomar_sedm (overhead 300 s, min altitude 30.0°, moon sep 30.0°).

## Composition

- **2025-04-19** coarse classes among BTS-classified pool members: {'Ia': 15, 'II': 2}; rejection reasons in superset: {'first_detection_before_window': 432, 'no_real_alert_le_t': 581, 'fainter_than_max_mag': 638, 'star_like_counterpart': 139, 'near_bright_star': 213, 'too_few_detections': 589, 'no_detection_le_t': 389, 'detections_too_close_in_time': 1459, 'galactic_plane': 49}; BTS-saved-by-t objects rejected at t: {'first_detection_before_window': 25, 'fainter_than_max_mag': 11, 'too_few_detections': 5, 'near_bright_star': 1}
- **2025-04-20** coarse classes among BTS-classified pool members: {'Ia': 18, 'II': 1, 'Ibc': 1}; rejection reasons in superset: {'first_detection_before_window': 244, 'no_real_alert_le_t': 612, 'fainter_than_max_mag': 669, 'star_like_counterpart': 137, 'near_bright_star': 228, 'too_few_detections': 625, 'no_detection_le_t': 423, 'detections_too_close_in_time': 1504, 'galactic_plane': 51}; BTS-saved-by-t objects rejected at t: {'first_detection_before_window': 21, 'near_bright_star': 1, 'too_few_detections': 2, 'fainter_than_max_mag': 7}
- **2025-04-21** coarse classes among BTS-classified pool members: {'Ia': 20, 'Ibc': 1}; rejection reasons in superset: {'first_detection_before_window': 432, 'no_real_alert_le_t': 660, 'fainter_than_max_mag': 714, 'star_like_counterpart': 141, 'near_bright_star': 264, 'too_few_detections': 668, 'no_detection_le_t': 457, 'detections_too_close_in_time': 1560, 'galactic_plane': 47}; BTS-saved-by-t objects rejected at t: {'first_detection_before_window': 7, 'near_bright_star': 1, 'too_few_detections': 3, 'fainter_than_max_mag': 7}
- **2025-04-22** coarse classes among BTS-classified pool members: {'Ibc': 2, 'Ia': 18}; rejection reasons in superset: {'first_detection_before_window': 464, 'no_real_alert_le_t': 727, 'fainter_than_max_mag': 803, 'star_like_counterpart': 154, 'near_bright_star': 303, 'too_few_detections': 744, 'no_detection_le_t': 483, 'detections_too_close_in_time': 1623, 'galactic_plane': 50}; BTS-saved-by-t objects rejected at t: {'first_detection_before_window': 10, 'fainter_than_max_mag': 14, 'too_few_detections': 2}
- **2025-04-23** coarse classes among BTS-classified pool members: {'Ia': 18, 'other_luminous': 1, 'Ibc': 1}; rejection reasons in superset: {'first_detection_before_window': 555, 'no_real_alert_le_t': 654, 'fainter_than_max_mag': 728, 'star_like_counterpart': 125, 'near_bright_star': 295, 'too_few_detections': 677, 'no_detection_le_t': 516, 'detections_too_close_in_time': 1525, 'galactic_plane': 43}; BTS-saved-by-t objects rejected at t: {'first_detection_before_window': 6, 'fainter_than_max_mag': 16, 'too_few_detections': 3}

Definitions: *bright SN-like* = pool member whose brightest qualifying detection at t is ≤ 18.5 mag and whose latest alert-time Fink SIMBAD crossmatch is not a stellar/AGN type (`scripts/m0_killtests.py:SN_LIKE_CDS_EXCLUDE`). *BTS saved by t* = in BTS with savedate ≤ t and first known detection (≤ t) inside the 14-day window, among superset objects. The full bright-regime recall diagnostic (denominator from BTS, not the superset) is `runs/m1/m1.1/recall_bright.md`. *Review-03:* this count-binding check includes contaminants and ignores feasibility; M3 re-verifies binding in spectrograph-hours (§6.3).
