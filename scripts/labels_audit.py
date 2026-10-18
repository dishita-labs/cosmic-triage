"""M1.1 contaminant stratification + human spot-check form (ARCHITECTURE §6.4 Review-03 (b)/(c), §10.3 M1.1).

Writes runs/reports/labels_audit.md, runs/m1/m1.1/labels_audit_form.csv and runs/m1/m1.1/contaminants.json.
Replay-side script (reads BTS truth). The owner does the looking; this script only prepares the sample, links and form.
Sherlock context comes from Lasair (needs LASAIR_TOKEN; batched, cached). Contaminant labels stay provisional until the
form is complete: if > 5% of the audited objects look like genuine SNe, the label rule tightens (§6.4 (c)).
Usage: uv run python scripts/labels_audit.py [--offline] [--seed 20261018] [--n 30]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import sys
from collections import Counter
from typing import Any

from cosmic_triage.ingest import AlerceClient, Cache, FinkClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient, known_sso_by_oid
from cosmic_triage.ingest.bts import BTSCatalog
from cosmic_triage.ingest.errors import CredentialMissing, OfflineCacheMiss
from cosmic_triage.ingest.lasair import LasairClient
from cosmic_triage.replay.labels import ClassMap, label_candidate
from cosmic_triage.replay.pool import ForwardPool, _f, night_t
from cosmic_triage.settings import PROJECT_ROOT, load_config

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from m0_killtests import SN_LIKE_CDS_EXCLUDE

OUT = PROJECT_ROOT / "runs" / "m1" / "m1.1"
AGN_CDS = {"QSO", "AGN", "Seyfert_1", "Seyfert_2", "Seyfert", "Blazar", "BLLac", "Candidate_AGN", "Candidate_QSO"}


def cds_group(cds: str | None) -> str:
    c = (cds or "Unknown").strip() or "Unknown"
    if c in ("Unknown", "Fail", "None"):
        return "no SIMBAD match"
    if c in AGN_CDS:
        return "AGN/QSO"
    if c in SN_LIKE_CDS_EXCLUDE:
        return "stellar/variable"
    if c in ("SN", "SN*", "Candidate_SN*"):
        return "SN (SIMBAD)"
    if c.startswith(("G", "Galaxy", "EmG", "Sy", "LINER", "Compact_Gr", "PairG", "GroupG", "ClG", "IG", "BClG", "RadioG",
                     "LSB_G", "HII_G", "StarburstG", "Candidate_G", "PartofG")) or c in ("Radio", "IR", "X", "UV", "Blue"):
        return "galaxy/extended"
    return f"other ({c})"


def age_bin(days: float) -> str:
    return "0–3 d" if days < 3 else ("3–7 d" if days < 7 else "7–14 d")


def offset_bin(sep: float | None) -> str:
    if sep is None:
        return "no host/offset"
    return "< 0.5″ (nuclear)" if sep < 0.5 else ("0.5–2″" if sep < 2.0 else "> 2″")


def links(oid: str, ra: float, dec: float) -> dict[str, str]:
    return {
        "ALeRCE": f"https://alerce.online/object/{oid}",
        "Lasair": f"https://lasair-ztf.lsst.ac.uk/objects/{oid}/",
        "Fink": f"https://fink-portal.org/{oid}",
        "TNS cone 5″": f"https://www.wis-tns.org/search?ra={ra:.6f}&decl={dec:.6f}&radius=5&coords_unit=arcsec",
        "Legacy Survey": f"https://www.legacysurvey.org/viewer?ra={ra:.6f}&dec={dec:.6f}&layer=ls-dr10&zoom=16&mark={ra:.6f},{dec:.6f}",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--seed", type=int, default=20261018)
    ap.add_argument("--n", type=int, default=30)
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    rcfg, _ = load_config("configs/replay/replay.yaml")
    cache = Cache()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache), workers=4)
    cfg = pool.cfg
    bts = BTSCatalog(cache)
    bts.load(str(rcfg["bts_snapshot_date"]))
    cmap = ClassMap()
    first_seen: dict[str, tuple[str, float]] = {}
    nights_in: dict[str, list[str]] = {}
    peaks: dict[str, float | None] = {}
    for n in rcfg["m1_nights"]:
        t = night_t(n, float(rcfg["decision_time_utc_hour"]))
        for oid, r in sorted(pool.evaluate_all(t).items()):
            if not r.passed:
                continue
            lab = label_candidate(oid, pool.raw(oid), bts, cmap, cfg.scored_peak_mag, cfg.min_drb)
            if lab.label != "contaminant":
                continue
            first_seen.setdefault(oid, (n, t))
            nights_in.setdefault(oid, []).append(n)
            peaks[oid] = lab.peak_mag
    oids = sorted(first_seen)
    sherlock: dict[str, dict[str, Any]] = {}
    sherlock_status = "ok"
    try:
        las = LasairClient(cache)
        las.prefetch(oids, "sherlock_classifications")
        sherlock = {o: rows[0] for o in oids if (rows := las.sherlock_object(o))}
    except CredentialMissing as exc:
        sherlock_status = str(exc)
    except OfflineCacheMiss:
        sherlock_status = "offline cache miss (run once online with LASAIR_TOKEN)"
    try:
        sso = known_sso_by_oid(pool.alerce_db, oids)
    except Exception as exc:  # diagnostic only
        sso, sherlock_status = {}, sherlock_status + f"; known-asteroid check unavailable ({type(exc).__name__})"
    recs: list[dict[str, Any]] = []
    for oid in oids:
        n, t = first_seen[oid]
        raw = pool.raw(oid)
        dets = raw.known_dets(t)
        rows = raw.fink_le(t)
        hs = raw.alert_hist_start(t)
        first = min([d["mjd"] for d in dets] + ([hs] if hs is not None else []))
        pos = raw.position_le(t)
        assert pos is not None
        sh = sherlock.get(oid, {})
        distnr = [v for d in dets if (v := _f(d.get("distnr"))) is not None and v >= 0]
        sh_sep = _f(sh.get("separationArcsec"))
        sep, sep_src = (sh_sep, "sherlock") if sh_sep is not None else (
            (statistics.median(distnr), "alerce distnr") if distnr else (None, "none"))
        cds = str(rows[-1].get("d:cdsxmatch") or "Unknown") if rows else "Unknown"
        recs.append({
            "oid": oid, "first_pool_night": n, "nights_in_pool": nights_in[oid], "ra": pos[0], "dec": pos[1],
            "qualifying_peak_full_history": peaks[oid], "history_age_days_at_t": t - first,
            "first_from_alert_history": hs is not None and hs < min(d["mjd"] for d in dets),
            "alert_ndethist_at_t": raw.alert_ndethist(t), "fink_cdsxmatch": cds, "cds_group": cds_group(cds),
            "sherlock_class": sh.get("classification") or ("(no row)" if sherlock_status == "ok" else "(unavailable)"),
            "sherlock_catalogue_type": sh.get("catalogue_object_type"), "sherlock_z": _f(sh.get("z")),
            "sherlock_photoz": _f(sh.get("photoZ")), "offset_arcsec": sep, "offset_source": sep_src,
            "links": links(oid, pos[0], pos[1]),
            "known_asteroid": next((f"{r['ssnamenr']} ({r['ssdistnr']:.1f}″)" for r in sso.get(oid, [])
                                    if r["ssdistnr"] is not None and 0 <= r["ssdistnr"] <= 12), None),
        })
    rng = random.Random(args.seed)
    sample = sorted(rng.sample(oids, min(args.n, len(oids))))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "contaminants.json").write_text(json.dumps({"seed": args.seed, "sample": sample, "sherlock_status": sherlock_status,
                                                       "prefilter_hash": cfg.config_hash, "records": recs}, indent=1))
    by = {r["oid"]: r for r in recs}
    with (OUT / "labels_audit_form.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["n", "oid", "alerce", "lasair", "fink", "tns_cone", "legacy_survey",
                    "verdict (SN / not SN / unsure)", "if not SN: what (asteroid/moving, AGN, CV, star, bogus, nuclear var., other)", "notes"])
        for i, o in enumerate(sample, 1):
            lk = by[o]["links"]
            w.writerow([i, o, lk["ALeRCE"], lk["Lasair"], lk["Fink"], lk["TNS cone 5″"], lk["Legacy Survey"], "", "", ""])

    def table(key: str, title: str) -> list[str]:
        c = Counter(r[key] for r in recs)
        return [f"**{title}**", "", "| Stratum | Contaminants | Share |", "|---|---|---|"] + [
            f"| {k} | {v} | {100 * v / len(recs):.0f}% |" for k, v in c.most_common()] + [""]

    for r in recs:
        r["age_bin"] = age_bin(r["history_age_days_at_t"])
        r["offset_bin"] = offset_bin(r["offset_arcsec"])
    L = [
        "# Labels audit — contaminant spot-check (M1.1)",
        "",
        "*Prepared by Opus for the owner. Status: **AWAITING OWNER REVIEW** — no human judgements recorded yet. "
        "Contaminant labels are provisional until this audit is complete (ARCHITECTURE §6.4, Review-03 (c)).*",
        "",
        "## What is being audited",
        "",
        "Rule under test (§6.4): a forward-pool member that BTS **never saved**, that passed the time-honest pre-filter, and "
        f"whose brightest *qualifying* detection (drb ≥ {cfg.min_drb}, positive subtraction) over its full history is ≤ "
        f"{cfg.scored_peak_mag} mag is labelled **contaminant** (justified by the BTS II TNS audit, ~0.6% missed SNe).",
        "",
        f"Population: **{len(recs)} unique contaminant objects** in the M1 nights {', '.join(rcfg['m1_nights'])} under pre-filter "
        f"`{cfg.config_hash}` (v{cfg.version}, known-at-t rule + per-alert history). Sample: **{len(sample)} objects** drawn "
        f"uniformly at random with `random.Random({args.seed})` (`scripts/labels_audit.py`).",
        "",
        "**Decision rule (pre-registered, §6.4 (c)):** if more than 5% of audited objects look like genuine SNe "
        f"(i.e. ≥ {int(0.05 * len(sample)) + 1} of {len(sample)}), the rule tightens to require non-SN contextual evidence "
        "and otherwise label the object **unknown**.",
        "",
        "## How to review (≈ 1–2 min per object)",
        "",
        "1. Open the ALeRCE or Lasair link: look at the light curve (rise/fall over weeks = SN-like; erratic or years-long "
        "variability = AGN/variable star; a pair of detections on one night and never again = moving object or bogus) and the "
        "cutout triplet.",
        "2. Open the TNS cone link: is there a TNS object at this position, and was it classified as an SN?",
        "3. Open Legacy Survey: is the source on a galaxy nucleus, offset in a galaxy, or a point source (star)?",
        "4. Fill in the verdict below (or in `runs/m1/m1.1/labels_audit_form.csv`). Please judge **before** reading the context "
        "section at the end, to avoid anchoring on the machine classifications.",
        "",
        "## Form",
        "",
        "| # | OID | Links | Verdict (SN / not SN / unsure) | If not SN: what (asteroid/moving, AGN, CV, star, bogus, nuclear var., other) | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for i, o in enumerate(sample, 1):
        lk = by[o]["links"]
        L.append(f"| {i} | `{o}` | " + " · ".join(f"[{k}]({v})" for k, v in lk.items()) + " | | | |")
    L += [
        "",
        "**Tally (owner):** genuine-looking SNe: ___ / " + str(len(sample)) + " · unsure: ___ · outcome: keep rule / tighten rule",
        "",
        "## Stratification of all contaminants (§6.4 (b))",
        "",
        "Strata are computed at each object's first pool night t from data known at t (history age, Fink crossmatch, "
        "offset from ALeRCE `distnr`), plus static Sherlock context from Lasair. Sherlock status: " + sherlock_status + ".",
        "",
    ]
    L += table("age_bin", "Alert-time history age (t − first detection incl. per-alert i:jdstarthist)")
    L += table("cds_group", "Fink alert-time SIMBAD crossmatch (d:cdsxmatch, grouped)")
    L += table("sherlock_class", "Sherlock classification (Lasair)")
    L += table("offset_bin", "Offset from host / nearest reference source (Sherlock separation, else ALeRCE distnr)")
    for r in recs:
        r["asteroid_bin"] = "known asteroid within 12″ (alert packet)" if r["known_asteroid"] else "no known asteroid match"
    L += table("asteroid_bin", "Known solar-system object at the position (alert-packet ssdistnr ≤ 12″, ALeRCE ss_ztf)")
    cross = Counter((r["sherlock_class"], r["offset_bin"]) for r in recs)
    L += ["**Sherlock class × offset**", "", "| Sherlock | Offset | n |", "|---|---|---|"] + [
        f"| {a} | {b} | {v} |" for (a, b), v in sorted(cross.items(), key=lambda x: -x[1])] + [""]
    L += [
        "## Context for the sampled objects (open after judging)",
        "",
        "<details><summary>Show machine context</summary>",
        "",
        "| # | OID | Pool nights | Qual. peak | Age at t (d) | Fink xmatch | Sherlock | Host z | Offset (src) | Known asteroid |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, o in enumerate(sample, 1):
        r = by[o]
        z = r["sherlock_z"] if r["sherlock_z"] is not None else r["sherlock_photoz"]
        L.append(f"| {i} | `{o}` | {len(r['nights_in_pool'])} | {r['qualifying_peak_full_history']:.2f} | "
                 f"{r['history_age_days_at_t']:.1f} | {r['fink_cdsxmatch']} | {r['sherlock_class']} | "
                 f"{'—' if z is None else f'{z:.3f}'} | {'—' if r['offset_arcsec'] is None else f'{r['offset_arcsec']:.2f}″'} "
                 f"({r['offset_source']}) | {r['known_asteroid'] or '—'} |")
    L += ["", "</details>", ""]
    (PROJECT_ROOT / "runs" / "reports" / "labels_audit.md").write_text("\n".join(L) + "\n")
    print(f"{len(recs)} contaminants; sample {len(sample)}; sherlock: {sherlock_status}; "
          f"sherlock rows {len(sherlock)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
