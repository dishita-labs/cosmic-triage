"""Generator for the adversarial leakage fixtures in tests/leakage/fixtures/ (§10.3 M1, §13.5).

Run once to (re)write the JSON files: `uv run python -m tests.leakage.make_fixtures`. Each fixture is a raw,
broker-shaped object (ALeRCE light curve + Fink rows + static context) seeded with one way future or truth
information could leak, plus the expectation the replay boundary must meet (absent or recomputed).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).parent / "fixtures"
T = 60766.8333333  # 2025-04-01 20:00 UTC
RA, DEC = 185.0, 30.0  # |b| ~ 83 deg


def det(mjd: float, mag: float, fid: int = 2, drb: float | None = 0.99, isdiffpos: str = "t", candid: int | None = None,
        ra: float = RA, dec: float = DEC, **extra: Any) -> dict[str, Any]:
    """A stamped alert detection (its own packet delivered it)."""
    d = {"mjd": mjd, "magpsf": mag, "sigmapsf": 0.05, "fid": fid, "drb": drb, "rb": 0.9, "isdiffpos": isdiffpos,
         "candid": candid or int(mjd * 1e5), "ra": ra, "dec": dec, "diffmaglim": 20.5, "has_stamp": True,
         "parent_candid": None}
    d.update(extra)
    return d


def prv(mjd: float, mag: float, parent_mjd: float, fid: int = 2, **extra: Any) -> dict[str, Any]:
    """A prv_candidates history detection (no stamp, no drb) delivered by the alert at ``parent_mjd``."""
    return det(mjd, mag, fid=fid, drb=None, has_stamp=False, parent_candid=int(parent_mjd * 1e5), **extra)


def nd(mjd: float, lim: float = 20.3, fid: int = 1) -> dict[str, Any]:
    return {"mjd": mjd, "fid": fid, "diffmaglim": lim, "tid": "ztf"}


def frow(mjd: float, **d: Any) -> dict[str, Any]:
    r = {"i:jd": mjd + 2400000.5, "i:candid": int(mjd * 1e5), "d:tag": "valid", "d:rf_snia_vs_nonia": 0.0,
         "d:snn_snia_vs_nonia": 0.5, "d:snn_sn_vs_all": 0.6, "d:cdsxmatch": "Unknown", "d:tns": "",
         "i:sgscore1": 0.03, "i:distpsnr1": 4.0, "i:srmag1": 20.1, "i:neargaia": 30.0, "i:maggaia": 19.0}
    r.update(d)
    return r


BASE = {
    "oid": "ZTF25leakbase",
    "lightcurve": {
        "detections": [det(T - 5.0, 18.6), det(T - 4.95, 18.5, fid=1), det(T - 2.0, 18.2)],
        "non_detections": [nd(T - 8.0), nd(T - 7.0)],
    },
    "fink_rows": [frow(T - 5.0), frow(T - 4.95), frow(T - 2.0)],
    "static": {"sgscore1": 0.03, "distpsnr1": 4.0, "srmag1": 20.1},
}


def make(name: str, desc: str, mutate: Any, expect: dict[str, Any], t: float = T) -> dict[str, Any]:
    f = copy.deepcopy(BASE)
    f["oid"] = "ZTF25" + name.replace("_", "")[:7]
    mutate(f)
    return {"name": name, "description": desc, "t_mjd": t, "raw": f, "expect": expect}


def fixtures() -> list[dict[str, Any]]:
    L: list[dict[str, Any]] = []

    def add(*a: Any, **k: Any) -> None:
        L.append(make(*a, **k))

    add("detection_t_plus_0p01d", "A detection at t + 0.01 d must be absent and counts recomputed.",
        lambda f: f["lightcurve"]["detections"].append(det(T + 0.01, 16.0)),
        {"n_detections": 3, "brightest_mag": 18.2, "member": True})
    add("detection_t_plus_1e-6d", "A detection one tenth of a second after t is still the future.",
        lambda f: f["lightcurve"]["detections"].append(det(T + 1e-6, 16.0)), {"n_detections": 3, "brightest_mag": 18.2})
    add("detection_exactly_at_t", "A detection exactly at t is the past (<= t) and is kept.",
        lambda f: f["lightcurve"]["detections"].append(det(T, 17.9)), {"n_detections": 4, "brightest_mag": 17.9})
    add("fink_row_jd_after_t", "A Fink row with jd > t must be absent.",
        lambda f: f["fink_rows"].append(frow(T + 0.5, **{"d:snn_snia_vs_nonia": 0.999})),
        {"n_fink_rows": 3, "forbidden_values": [0.999]})
    add("fink_tns_label_after_t", "Fink's alert-time TNS label from a later alert must not leak.",
        lambda f: f["fink_rows"].append(frow(T + 1.0, **{"d:tns": "SN Ia"})), {"forbidden_strings": ["SN Ia"]})
    add("bts_type_field", "A BTS `type` (and redshift) joined onto raw records must be absent.",
        lambda f: [d.update({"type": "SN Ia-91T", "redshift": 0.0345}) for d in f["lightcurve"]["detections"]],
        {"forbidden_strings": ["SN Ia-91T"], "forbidden_values": [0.0345], "forbidden_keys": ["type", "redshift"]})
    add("ndethist_final_history", "`ndethist`/`ncovhist` from the final history must be absent; count recomputed.",
        lambda f: [d.update({"ndethist": 57, "ncovhist": 812}) for d in f["lightcurve"]["detections"]],
        {"n_detections": 3, "forbidden_keys": ["ndethist", "ncovhist"], "forbidden_values": [57, 812]})
    add("nondetection_after_t", "An upper limit after t must be absent.",
        lambda f: f["lightcurve"]["non_detections"].append(nd(T + 0.3, 21.7)),
        {"n_nondetections": 2, "forbidden_values": [21.7]})
    add("alerce_class_probability", "ALeRCE current-state `class`/`probability`/`classifier` must be absent.",
        lambda f: [d.update({"class": "SNIa", "probability": 0.871, "classifier": "lc_classifier"})
                   for d in f["lightcurve"]["detections"]],
        {"forbidden_strings": ["SNIa", "lc_classifier"], "forbidden_values": [0.871]})
    add("peak_fields", "Any `peak*` field (BTS peakt/peakmag/peakabs) must be absent.",
        lambda f: [d.update({"peakmag": 17.123, "peakt": 2766.4, "peakabs": -19.3}) for d in f["lightcurve"]["detections"]],
        {"forbidden_values": [17.123, 2766.4, -19.3], "forbidden_keys": ["peakmag", "peakt", "peakabs"]})
    add("fink_object_aggregates", "Fink object-level `v:*` aggregates (final) must be absent.",
        lambda f: [r.update({"v:classification": "Early SN Ia candidate", "v:lastdate": "2025-05-01"}) for r in f["fink_rows"]],
        {"forbidden_strings": ["Early SN Ia candidate", "2025-05-01"]})
    add("fink_lc_features", "Fink `d:lc_features_*` (computed over the full light curve) must be absent.",
        lambda f: [r.update({"d:lc_features_g": "[18.123456, 0.5]"}) for r in f["fink_rows"]],
        {"forbidden_strings": ["18.123456"]})
    add("future_position_shift", "The position is the mean of detections <= t only; a later offset detection is ignored.",
        lambda f: f["lightcurve"]["detections"].append(det(T + 2.0, 18.0, ra=RA + 0.01, dec=DEC + 0.01)),
        {"ra": RA, "dec": DEC})
    add("mjdstarthist_final", "A final `mjdstarthist` (older history learned later) must be absent; first detection recomputed.",
        lambda f: [d.update({"mjdstarthist": T - 400.0, "jdstarthist": T - 400.0 + 2400000.5}) for d in f["lightcurve"]["detections"]],
        {"first_detection_mjd": T - 5.0, "member": True, "forbidden_keys": ["mjdstarthist", "jdstarthist"]})
    add("single_detection_by_t", "Only one detection by t (the rest later) -> not in the pool at t.",
        lambda f: f["lightcurve"].update(detections=[det(T - 0.5, 18.4), det(T + 0.5, 18.3), det(T + 1.0, 18.1)]),
        {"member": False})
    add("bright_only_after_t", "Brighter than 19 only after t -> not in the pool at t.",
        lambda f: f["lightcurve"].update(detections=[det(T - 3.0, 19.6), det(T - 2.9, 19.5), det(T + 1.0, 17.5)]),
        {"member": False})
    add("separation_only_after_t", "Two detections < 30 min apart by t; the separating third is after t -> not in pool.",
        lambda f: f["lightcurve"].update(detections=[det(T - 1.0, 18.4), det(T - 1.0 + 10 / 1440, 18.4), det(T + 1.0, 18.0)]),
        {"member": False})
    add("low_drb_by_t", "Detections by t fail drb >= 0.5; the real-looking ones come later -> not in pool.",
        lambda f: f["lightcurve"].update(detections=[det(T - 3.0, 18.2, drb=0.1), det(T - 2.0, 18.1, drb=0.2),
                                                     det(T + 1.0, 18.0), det(T + 2.0, 17.9)]),
        {"member": False})
    add("brightest_after_t", "Brightest magnitude is recomputed from <= t (a brighter later point is ignored).",
        lambda f: f["lightcurve"]["detections"].append(det(T + 3.0, 15.5)), {"brightest_mag": 18.2})
    add("latest_mag_after_t", "Latest magnitude is the last detection <= t, not the final one.",
        lambda f: f["lightcurve"]["detections"].append(det(T + 0.2, 17.0, fid=1)), {"latest_mag": 18.2, "latest_band": "r"})
    add("negative_subtraction", "A negative-subtraction detection does not set the brightest magnitude.",
        lambda f: f["lightcurve"]["detections"].append(det(T - 1.0, 16.0, isdiffpos="f")), {"brightest_mag": 18.2})
    add("bts_savedate_iauid", "BTS `savedate`/`IAUID` joined onto raw records must be absent.",
        lambda f: [d.update({"savedate": "2025-04-03T05:00:00", "IAUID": "SN2025zzz"}) for d in f["lightcurve"]["detections"]],
        {"forbidden_strings": ["2025-04-03T05:00:00", "SN2025zzz"]})
    add("window_first_detection_old", "First detection <= t is older than 14 d -> not in the forward pool.",
        lambda f: f["lightcurve"]["detections"].insert(0, det(T - 20.0, 19.4)), {"member": False})
    add("future_only_object", "An object whose first detection is after t must not appear at all.",
        lambda f: f["lightcurve"].update(detections=[det(T + 0.1, 18.0), det(T + 0.2, 18.0)]),
        {"member": False, "no_snapshot": True})
    add("history_without_drb_counts", "A prv_candidates history detection (no drb) counts toward the history; the alert passes drb.",
        lambda f: f["lightcurve"].update(detections=[prv(T - 3.0, 18.9, parent_mjd=T - 2.0), det(T - 2.0, 18.4)]),
        {"member": True, "n_detections": 2})
    add("no_real_alert_only_history", "History-only detections (no drb anywhere by t) never make an object a pool member.",
        lambda f: f["lightcurve"].update(detections=[prv(T - 3.0, 18.4, parent_mjd=T + 0.5), prv(T - 2.0, 18.3, parent_mjd=T + 0.5),
                                                     det(T + 0.5, 18.0)]),
        {"member": False, "no_snapshot": True})
    # --- M1.1 (Review-03): known-at-t delivery rule and per-alert history fields -------------------------------------
    add("prv_delivered_after_t", "(i) A prv detection with mjd <= t delivered only by an alert with jd > t is excluded.",
        lambda f: f["lightcurve"]["detections"].extend([prv(T - 1.0, 17.31, parent_mjd=T + 0.5), det(T + 0.5, 17.2)]),
        {"n_detections": 3, "brightest_mag": 18.2, "latest_mag": 18.2, "forbidden_values": [17.31]})
    add("nondet_older_than_any_delivering_alert", "(ii) A non-detection older than the 30-day history of every alert <= t is excluded.",
        lambda f: f["lightcurve"]["non_detections"].insert(0, nd(T - 40.0, 21.37)),
        {"n_nondetections": 2, "forbidden_values": [21.37]})
    add("nondet_after_last_alert_le_t", "(ii) A non-detection after the last alert <= t (delivered only by a later packet) is excluded.",
        lambda f: (f["lightcurve"]["non_detections"].append(nd(T - 1.0, 21.41)),
                   f["lightcurve"]["detections"].append(det(T + 0.4, 18.1))),
        {"n_nondetections": 2, "forbidden_values": [21.41]})
    add("alert_jdstarthist_before_window", "(iii) Alert-time i:jdstarthist before the window -> rejected (first_detection_before_window).",
        lambda f: [r.update({"i:jdstarthist": T - 200.0 + 2400000.5, "i:ndethist": 41}) for r in f["fink_rows"]],
        {"member": False, "reasons_include": ["first_detection_before_window"], "first_detection_mjd": T - 200.0})
    add("fink_row_after_t_with_old_jdstarthist", "(iv) A Fink row with jd > t carrying an earlier i:jdstarthist is ignored.",
        lambda f: f["fink_rows"].append(frow(T + 0.5, **{"i:jdstarthist": T - 200.0 + 2400000.5, "i:ndethist": 77})),
        {"member": True, "first_detection_mjd": T - 5.0, "n_fink_rows": 3, "forbidden_values": [77]})
    add("object_level_hist_in_alerce", "(v) Object-level jdstarthist/ndethist injected into ALeRCE records are still scrubbed.",
        lambda f: [d.update({"jdstarthist": T - 300.0 + 2400000.5, "ndethist": 99, "i:jdstarthist": T - 300.0 + 2400000.5,
                             "i:ndethist": 99}) for d in f["lightcurve"]["detections"]],
        {"member": True, "first_detection_mjd": T - 5.0, "forbidden_values": [99, T - 300.0 + 2400000.5],
         "forbidden_keys": ["jdstarthist", "ndethist", "i:jdstarthist", "i:ndethist"]})
    add("per_alert_ndethist_counts", "Per-alert i:ndethist / jd - i:jdstarthist (rows <= t) supply the history like the BTS filter.",
        lambda f: (f["lightcurve"].update(detections=[det(T - 1.0, 18.3)]),
                   f.update(fink_rows=[frow(T - 1.0, **{"i:jdstarthist": T - 1.5 + 2400000.5, "i:ndethist": 3})])),
        {"member": True, "n_detections": 1, "first_detection_mjd": T - 1.5})
    add("jdstarthist_after_row_jd_ignored", "A corrupt per-alert i:jdstarthist later than its own row's jd is ignored.",
        lambda f: [r.update({"i:jdstarthist": r["i:jd"] + 3.0}) for r in f["fink_rows"]],
        {"member": True, "first_detection_mjd": T - 5.0})
    add("prv_delivered_by_alert_le_t", "A prv detection delivered by an alert <= t is known and attributed to that alert.",
        lambda f: f["lightcurve"]["detections"].append(prv(T - 4.5, 18.35, parent_mjd=T - 2.0)),
        {"n_detections": 4, "delivered_by": {"18.35": T - 2.0}})
    add("prv_unresolvable_parent", "A prv detection whose parent alert is unknown cannot be shown to be known -> excluded.",
        lambda f: f["lightcurve"]["detections"].append(prv(T - 4.5, 18.36, parent_mjd=T - 9.123)),
        {"n_detections": 3, "forbidden_values": [18.36]})
    add("prv_later_parent_does_not_move_first_detection", "An old prv detection delivered after t does not set the first detection.",
        lambda f: f["lightcurve"]["detections"].insert(0, prv(T - 10.0, 19.4, parent_mjd=T + 1.0)),
        {"member": True, "first_detection_mjd": T - 5.0, "n_detections": 3})
    return L


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, fx in enumerate(fixtures(), 1):
        (OUT / f"{i:02d}_{fx['name']}.json").write_text(json.dumps(fx, indent=1) + "\n")
    print(f"wrote {i} fixtures to {OUT}")


if __name__ == "__main__":
    main()
