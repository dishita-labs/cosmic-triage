# M1.1 bright-regime recall diagnostic

Denominator per night t: BTS objects with peak ≤ 18.5 saved by t whose ALeRCE first detection is in [t − 14 d, t]. Pre-filter `9669bcad8c932e03` (v1.1). Replay-side diagnostic (reads truth).

| Night | Denominator | Reached pool | Recall |
|---|---|---|---|
| 2025-04-19 | 35 | 17 | 48.6% |
| 2025-04-20 | 30 | 20 | 66.7% |
| 2025-04-21 | 23 | 16 | 69.6% |
| 2025-04-22 | 27 | 15 | 55.6% |
| 2025-04-23 | 28 | 17 | 60.7% |
| **all** | **143** | **85** | **59.4%** |

## Misses (object-night pairs)

| Night | OID | Stage | Reasons | BTS type | BTS peak (mjd) | Saved | Brightest qual. at t | Brightest qual. ever | n_hist at t |
|---|---|---|---|---|---|---|---|---|---|
| 2025-04-19 | ZTF25aalldzz | prefilter | first_detection_before_window | SN Ia | 17.31 (60772.4) | 60774.4 | 17.31 | 17.31 | 11 |
| 2025-04-19 | ZTF25aalpzgd | prefilter | first_detection_before_window | SN II | 18.47 (60775.4) | 60771.5 | 18.47 | 18.47 | 25 |
| 2025-04-19 | ZTF25aaluens | prefilter | first_detection_before_window | SN Ia | 17.28 (60775.4) | 60772.4 | 17.28 | 17.28 | 19 |
| 2025-04-19 | ZTF25aaluerd | prefilter | first_detection_before_window | SN II | 18.24 (60786.4) | 60773.3 | 18.27 | 18.24 | 28 |
| 2025-04-19 | ZTF25aalufla | prefilter | first_detection_before_window | SN Ia | 18.02 (60776.4) | 60772.5 | 18.02 | 18.02 | 16 |
| 2025-04-19 | ZTF25aalughb | prefilter | first_detection_before_window | SN Ia | 15.87 (60785.3) | 60773.5 | 16.36 | 15.87 | 14 |
| 2025-04-19 | ZTF25aalvbwm | superset | superset:every_ps1_row_star_like | SN II | 17.59 (60775.4) | 60772.5 | 17.59 | 17.59 | 4 |
| 2025-04-19 | ZTF25aalyfoi | prefilter | first_detection_before_window | SN II | 16.86 (60775.4) | 60775.4 | 16.86 | 16.86 | 21 |
| 2025-04-19 | ZTF25aalziig | superset | superset:every_ps1_row_star_like | SN Ia | 17.91 (60781.4) | 60773.5 | 17.91 | 17.91 | 14 |
| 2025-04-19 | ZTF25aamgkfe | superset | superset:every_ps1_row_star_like | SN Ia | 16.92 (60774.4) | 60776.3 | 16.92 | 16.92 | 3 |
| 2025-04-19 | ZTF25aamhjku | prefilter | too_few_detections, fainter_than_max_mag | SN Ic | 18.28 (60787.5) | 60774.9 | 19.14 | 18.28 | 1 |
| 2025-04-19 | ZTF25aamhqoo | prefilter | fainter_than_max_mag | SN II | 17.86 (60785.5) | 60774.6 | 19.13 | 17.86 | 7 |
| 2025-04-19 | ZTF25aanbchm | prefilter | too_few_detections, fainter_than_max_mag | SN Ia | 18.16 (60795.2) | 60781.4 | 19.25 | 18.16 | 1 |
| 2025-04-19 | ZTF25aanbcou | prefilter | too_few_detections, fainter_than_max_mag | SN Ia | 18.26 (60795.2) | 60781.3 | 19.58 | 18.26 | 1 |
| 2025-04-19 | ZTF25aanbdft | prefilter | fainter_than_max_mag | SN Ia | 18.40 (60787.2) | 60780.3 | 19.00 | 18.40 | 2 |
| 2025-04-19 | ZTF25aanbqrx | prefilter | first_detection_before_window | - | 18.35 (60788.3) | 60780.4 | 18.82 | 18.35 | 6 |
| 2025-04-19 | ZTF25aanbrxz | prefilter | too_few_detections, fainter_than_max_mag | - | 18.37 (60789.3) | 60780.3 | 19.76 | 18.37 | 1 |
| 2025-04-19 | ZTF25aanezba | prefilter | fainter_than_max_mag | SN Ia-91bg | 16.88 (60797.2) | 60781.3 | 19.17 | 16.88 | 2 |
| 2025-04-20 | ZTF25aalldzz | prefilter | first_detection_before_window | SN Ia | 17.31 (60772.4) | 60774.4 | 17.31 | 17.31 | 11 |
| 2025-04-20 | ZTF25aalrrwj | prefilter | first_detection_before_window | SN Ia | 17.47 (60774.4) | 60772.4 | 17.47 | 17.47 | 5 |
| 2025-04-20 | ZTF25aalufla | prefilter | first_detection_before_window | SN Ia | 18.02 (60776.4) | 60772.5 | 18.02 | 18.02 | 24 |
| 2025-04-20 | ZTF25aalughb | prefilter | first_detection_before_window | SN Ia | 15.87 (60785.3) | 60773.5 | 15.87 | 15.87 | 22 |
| 2025-04-20 | ZTF25aalvbwm | superset | superset:every_ps1_row_star_like | SN II | 17.59 (60775.4) | 60772.5 | 17.59 | 17.59 | 4 |
| 2025-04-20 | ZTF25aamgkfe | superset | superset:every_ps1_row_star_like | SN Ia | 16.92 (60774.4) | 60776.3 | 16.92 | 16.92 | 3 |
| 2025-04-20 | ZTF25aamhjku | prefilter | too_few_detections, fainter_than_max_mag | SN Ic | 18.28 (60787.5) | 60774.9 | 19.14 | 18.28 | 1 |
| 2025-04-20 | ZTF25aanbnfj | prefilter | first_detection_before_window | SN Ia | 18.08 (60799.2) | 60785.4 | 18.28 | 18.10 | 4 |
| 2025-04-20 | ZTF25aanbqrx | prefilter | first_detection_before_window | - | 18.35 (60788.3) | 60780.4 | 18.45 | 18.35 | 11 |
| 2025-04-20 | ZTF25aanezba | prefilter | fainter_than_max_mag | SN Ia-91bg | 16.88 (60797.2) | 60781.3 | 19.17 | 16.88 | 2 |
| 2025-04-21 | ZTF25aaluvkb | prefilter | first_detection_before_window | SN Ia | 17.75 (60785.3) | 60773.5 | 17.75 | 17.75 | 10 |
| 2025-04-21 | ZTF25aaluyhj | prefilter | first_detection_before_window | SN Ia | 18.21 (60781.4) | 60773.5 | 18.21 | 18.21 | 12 |
| 2025-04-21 | ZTF25aamgkfe | superset | superset:every_ps1_row_star_like | SN Ia | 16.92 (60774.4) | 60776.3 | 16.92 | 16.92 | 4 |
| 2025-04-21 | ZTF25aamhjku | prefilter | too_few_detections, fainter_than_max_mag | SN Ic | 18.28 (60787.5) | 60774.9 | 19.14 | 18.28 | 1 |
| 2025-04-21 | ZTF25aanbnfj | prefilter | first_detection_before_window | SN Ia | 18.08 (60799.2) | 60785.4 | 18.28 | 18.10 | 4 |
| 2025-04-21 | ZTF25aanbqrx | prefilter | first_detection_before_window | - | 18.35 (60788.3) | 60780.4 | 18.45 | 18.35 | 11 |
| 2025-04-21 | ZTF25aanpvix | superset | superset:every_ps1_row_star_like | SN II | 17.90 (60790.4) | 60786.5 | 18.43 | 17.90 | 2 |
| 2025-04-22 | ZTF25aambsqu | prefilter | first_detection_before_window | SN Ia | 18.15 (60787.5) | 60776.5 | 18.15 | 18.15 | 14 |
| 2025-04-22 | ZTF25aameuts | prefilter | first_detection_before_window | SN Ia | 17.63 (60786.2) | 60776.3 | 17.63 | 17.63 | 6 |
| 2025-04-22 | ZTF25aamgkfe | superset | superset:every_ps1_row_star_like | SN Ia | 16.92 (60774.4) | 60776.3 | 16.92 | 16.92 | 4 |
| 2025-04-22 | ZTF25aanblle | superset | superset:every_ps1_row_star_like | SN Ia | 18.47 (60789.2) | 60787.2 | 18.57 | 18.47 | 2 |
| 2025-04-22 | ZTF25aanbnfj | prefilter | first_detection_before_window | SN Ia | 18.08 (60799.2) | 60785.4 | 18.10 | 18.10 | 5 |
| 2025-04-22 | ZTF25aanlfdo | prefilter | fainter_than_max_mag | SN Ia | 18.48 (60795.3) | 60786.5 | 19.60 | 18.48 | 8 |
| 2025-04-22 | ZTF25aanmfji | prefilter | fainter_than_max_mag | SN Ib | 18.09 (60804.5) | 60786.5 | 19.38 | 18.09 | 3 |
| 2025-04-22 | ZTF25aanmrqp | superset | superset:every_ps1_row_star_like | SN Ia | 18.26 (60795.2) | 60787.7 | 18.80 | 18.26 | 2 |
| 2025-04-22 | ZTF25aanpvix | superset | superset:every_ps1_row_star_like | SN II | 17.90 (60790.4) | 60786.5 | 18.43 | 17.90 | 2 |
| 2025-04-22 | ZTF25aantkpx | prefilter | fainter_than_max_mag | - | 18.39 (60798.2) | 60787.3 | 19.68 | 18.39 | 2 |
| 2025-04-22 | ZTF25aanvpit | prefilter | first_detection_before_window, fainter_than_max_mag | SN Ia | 18.04 (60798.4) | 60787.4 | 19.51 | 18.04 | 13 |
| 2025-04-22 | ZTF25aanxipy | superset | superset:every_ps1_row_star_like, (ALeRCE-only at t: detections_too_close_in_time) | SN Ia | 18.11 (60796.4) | 60787.4 | 18.49 | 18.11 | 2 |
| 2025-04-23 | ZTF25aanblle | superset | superset:every_ps1_row_star_like | SN Ia | 18.47 (60789.2) | 60787.2 | 18.57 | 18.47 | 2 |
| 2025-04-23 | ZTF25aanbnfj | prefilter | first_detection_before_window | SN Ia | 18.08 (60799.2) | 60785.4 | 18.10 | 18.10 | 5 |
| 2025-04-23 | ZTF25aanlfdo | prefilter | fainter_than_max_mag | SN Ia | 18.48 (60795.3) | 60786.5 | 19.60 | 18.48 | 8 |
| 2025-04-23 | ZTF25aanmfji | prefilter | fainter_than_max_mag | SN Ib | 18.09 (60804.5) | 60786.5 | 19.38 | 18.09 | 3 |
| 2025-04-23 | ZTF25aanmrqp | superset | superset:every_ps1_row_star_like | SN Ia | 18.26 (60795.2) | 60787.7 | 18.77 | 18.26 | 3 |
| 2025-04-23 | ZTF25aanpvix | superset | superset:every_ps1_row_star_like | SN II | 17.90 (60790.4) | 60786.5 | 18.15 | 17.90 | 3 |
| 2025-04-23 | ZTF25aantkpx | prefilter | fainter_than_max_mag | - | 18.39 (60798.2) | 60787.3 | 19.68 | 18.39 | 2 |
| 2025-04-23 | ZTF25aanvpit | prefilter | first_detection_before_window, fainter_than_max_mag | SN Ia | 18.04 (60798.4) | 60787.4 | 19.51 | 18.04 | 13 |
| 2025-04-23 | ZTF25aanxipy | superset | superset:every_ps1_row_star_like, (ALeRCE-only at t: detections_too_close_in_time) | SN Ia | 18.11 (60796.4) | 60787.4 | 18.49 | 18.11 | 2 |
| 2025-04-23 | ZTF25aaoaeki | prefilter | fainter_than_max_mag | - | 18.25 (60795.5) | 60788.5 | 19.12 | 18.25 | 3 |
| 2025-04-23 | ZTF25aaocnsp | prefilter | too_few_detections, fainter_than_max_mag | SN Ia | 17.30 (60805.2) | 60788.4 | 19.67 | 17.30 | 1 |

Miss reasons (counts over object-nights): {'first_detection_before_window': 24, 'superset:every_ps1_row_star_like': 16, 'too_few_detections': 7, 'fainter_than_max_mag': 20}
