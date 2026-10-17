"""M0 feasibility / kill-tests (ARCHITECTURE §11). Writes runs/m0/killtests.{md,json}.

Every test records one verdict:
  PASS | FAIL | PARTIAL | BLOCKED: CREDENTIAL REQUIRED | DEFERRED (by architecture: tested in a later milestone)
Failures of #1-#5 need a Fable decision (§14.7); this script never picks those fallbacks itself.

Usage: uv run python scripts/m0_killtests.py [--only 1,2,9] [--offline]
No paid model calls are made (owner has not approved a spend budget).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import traceback
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from cosmic_triage import settings
from cosmic_triage.ingest import AlerceClient, Cache, CredentialMissing, FinkClient, LasairClient, TNSClient
from cosmic_triage.ingest.catalogs import NedClient, SimbadClient
from cosmic_triage.ingest.corpora import AstroNoteClient, AtelClient, GcnClient
from cosmic_triage.settings import PROJECT_ROOT, load_config

OUT = PROJECT_ROOT / "runs" / "m0"

# Probe objects (public, BTS-classified 2025 SNe Ia) used across tests; chosen during M0 probing.
PROBE_SN = "ZTF25aaafbbk"  # SN 2025N, SN Ia in UGC 08239
PROBE_SN_RA, PROBE_SN_DEC = 197.33599, 46.23975  # mean ALeRCE detection position


@dataclass
class Verdict:
    id: int
    assumption: str
    test: str
    verdict: str
    evidence: list[str] = field(default_factory=list)
    fallback: str = ""
    needs_fable: bool = False
    credential: str = ""
    setup: str = ""
    seconds: float = 0.0


def kt1_tns(cache: Cache) -> Verdict:
    v = Verdict(1, "TNS report/classification dates obtainable (individual bot)", "register; one query", "")
    tns = TNSClient(cache)
    try:
        rows = tns.search(PROBE_SN_RA, PROBE_SN_DEC, 3.0)
        obj = tns.get_object(rows[0]["objname"]) if rows else {}
        v.evidence.append(f"search returned {len(rows)} rows; object keys: {sorted(obj)[:12]}")
        has_dates = any(k in obj for k in ("discoverydate", "classification_date", "classification_reports"))
        v.verdict = "PASS" if has_dates else "FAIL"
    except CredentialMissing as exc:
        v.verdict = "BLOCKED: CREDENTIAL REQUIRED"
        v.credential = exc.name
        v.setup = exc.how
        v.evidence.append("No TNS bot credentials in .env; no TNS call was attempted.")
    # Inspect the fallback's shape (informational only; choosing it is a Fable decision).
    try:
        las = LasairClient(cache)
        xm = las.tns_crossmatch(PROBE_SN)
        cols = sorted(xm[0]) if xm else []
        v.evidence.append(
            f"Fallback inspected (not adopted): Lasair crossmatch_tns for {PROBE_SN} -> "
            f"{[(r.get('tns_name'), r.get('type'), r.get('disc_date')) for r in xm]}; columns={cols}. "
            "It has disc_date and lastmodified_date but NO classification date, and `type` is the current TNS type."
        )
    except Exception as exc:
        v.evidence.append(f"Fallback inspection failed: {type(exc).__name__}: {exc}")
    v.fallback = "Lasair/Fink TNS crossmatch tables (dates partial) — requires Fable decision (§14.7) if TNS stays unavailable"
    v.needs_fable = v.verdict != "PASS"
    return v


def kt2_fink(cache: Cache) -> Verdict:
    v = Verdict(2, "Fink /objects POST returns per-alert d:* incl. d:tns, with upper limits", "one POST", "")
    fink = FinkClient(cache)
    rows = fink.object_rows(PROBE_SN, with_upperlim=True)
    tags = Counter(r.get("d:tag") for r in rows)
    valid = [r for r in rows if r.get("d:tag") == "valid"]
    need = ["d:rf_snia_vs_nonia", "d:snn_snia_vs_nonia", "d:snn_sn_vs_all", "d:cdsxmatch", "d:tns"]
    missing = [k for k in need if not valid or k not in valid[0]]
    jds = sorted(r["i:jd"] for r in valid)
    per_alert = len(valid) >= 2 and len(set(jds)) == len(jds)
    tns_series = [(round(r["i:jd"] - 2460000, 2), r.get("d:tns")) for r in sorted(valid, key=lambda r: r["i:jd"])][:6]
    v.evidence += [
        f"{PROBE_SN}: {len(rows)} rows, tags={dict(tags)}; distinct alert jd per valid row: {per_alert}",
        f"missing required fields: {missing or 'none'}",
        f"d:tns over time (jd-2460000, value): {tns_series} — changes from '' to a class after the TNS report, "
        "consistent with alert-time crossmatch semantics",
    ]
    # Known quirk seen during probing: withupperlim=True can return [] for an object that has rows.
    quirk = fink.object_rows("ZTF25aaaalin", with_upperlim=True)
    quirk2 = fink.object_rows("ZTF25aaaalin", with_upperlim=False)
    v.evidence.append(
        f"quirk check ZTF25aaaalin: withupperlim=True -> {len(quirk)} rows; withupperlim=False -> {len(quirk2)} rows "
        "(during M0 probing the withupperlim=True call once returned [] for this object — transient). "
        "Mitigation: upper limits are taken from ALeRCE light curves; Fink is used for alert-time scores only."
    )
    ok = not missing and per_alert and tags.get("upperlim", 0) > 0
    v.verdict = "PASS" if ok else "FAIL"
    v.fallback = "ALeRCE + stamp prior only (requires Fable decision, §14.7)" if not ok else ""
    v.needs_fable = not ok
    return v


def _pool(cache: Cache) -> Any:
    from cosmic_triage.ingest.alerce_db import AlerceDBClient
    from cosmic_triage.replay.pool import ForwardPool

    return ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache))


SN_LIKE_CDS_EXCLUDE = {
    "Star", "*", "V*", "EB*", "RRLyr", "CV*", "QSO", "AGN", "Seyfert_1", "Seyfert_2", "Seyfert", "Blazar", "BLLac",
    "YSO", "Mira", "LPV*", "RGB*", "WD*", "PM*", "HighPM*", "low-mass*", "BYDra", "RSCVn", "Cepheid", "delSctV*",
    "Orion_V*", "TTau*", "Em*", "C*", "Be*", "Pulsating*", "EllipVar", "Candidate_EB*", "Candidate_CV*",
    "Candidate_RRLyr", "Candidate_YSO", "Candidate_LP*", "Candidate_AGN", "Candidate_QSO", "Candidate_TTau*",
    "Candidate_WD*", "Candidate_brownD*", "Candidate_Hsd", "brownD*", "Variable*", "Irregular_V*", "SB*",
    "Ae*", "AGB*", "post-AGB*", "HB*", "HS*", "Hsd", "BlueStraggler", "Symbiotic*", "XB", "LMXB", "HMXB", "Nova",
    "gammaDor", "RotV*", "S*", "Mi*", "OH/IR", "LP*", "WR*", "BlueSG", "RedSG", "YellowSG", "Ce*", "sdB", "Gaia DR3",
}


def sn_like(raw: Any, t: float) -> bool:
    rows = [r for r in raw.fink_rows if r["mjd"] <= t]
    if not rows:
        return True
    cds = str(rows[-1].get("d:cdsxmatch") or "Unknown")
    return cds not in SN_LIKE_CDS_EXCLUDE


def kt3_pool_volume(cache: Cache) -> Verdict:
    from cosmic_triage.replay.pool import night_t

    v = Verdict(3, "Forward-pool volume per night manageable (<= ~500 after pre-filter)", "5 nights of /objects?firstmjd", "")
    rcfg, _ = load_config("configs/replay/replay.yaml")
    pool = _pool(cache)
    sizes = {}
    raw_counts = {}
    for night in rcfg["m1_nights"]:
        t = night_t(night, float(rcfg["decision_time_utc_hour"]))
        res = pool.evaluate_all(t)
        sizes[night] = sum(r.passed for r in res.values())
        day = int(t)
        raw_counts[night] = (len(pool.alerce.objects((day, day + 1), ndet=[2, 100000])), len(pool.superset_day(day)), len(res))
    med = statistics.median(sizes.values())
    v.evidence += [
        f"pool size after time-honest pre-filter per night: {sizes} (median {med})",
        "per night: ALeRCE objects first alerted that UTC day with final ndet>=2 (REST /objects?firstmjd) / that day's "
        "superset after necessary cuts (all-time brightest <= 19, |b|, PS1 star) / 15-day window superset hydrated: "
        + ", ".join(f"{n}: {a}/{b}/{c}" for n, (a, b, c) in raw_counts.items()),
    ]
    v.verdict = "PASS" if med <= 500 else "FAIL"
    v.fallback = "" if med <= 500 else "tighten pre-filter / cache more (requires Fable decision, §14.7)"
    v.needs_fable = med > 500
    return v


def kt4_budget(cache: Cache) -> Verdict:
    from cosmic_triage.replay.pool import night_t

    v = Verdict(4, "Budget binds: median(bright SN-like candidates)/slots >= 2", "count over candidate window", "")
    rcfg, _ = load_config("configs/replay/replay.yaml")
    pcfg, _ = load_config("configs/replay/prefilter.yaml")
    pool = _pool(cache)
    counts = {}
    for night in rcfg["m1_nights"]:
        t = night_t(night, float(rcfg["decision_time_utc_hour"]))
        res = pool.evaluate_all(t)
        counts[night] = sum(
            1 for oid, r in res.items()
            if r.passed and r.brightest_mag is not None and r.brightest_mag <= float(pcfg["scored_peak_mag"])
            and sn_like(pool.raw(oid), t)
        )
    med = statistics.median(counts.values())
    bmax = int(med // 2)
    v.evidence += [
        f"bright (brightest qualifying mag <= {pcfg['scored_peak_mag']} at t) & SN-like (latest alert-time Fink "
        f"cdsxmatch not stellar/AGN) pool members per night: {counts}; median {med}",
        f"largest budget with median/slots >= 2: {bmax} spectra/night "
        "(architecture floor if the sky is thin: 3-4 spectra/night)",
    ]
    v.verdict = "PASS" if bmax >= 3 else "FAIL"
    v.fallback = "" if bmax >= 3 else "shrink budget below 3 (requires Fable decision, §14.7)"
    v.needs_fable = bmax < 3
    return v


def kt5_bts(cache: Cache) -> Verdict:
    from cosmic_triage.ingest.bts import BTSCatalog

    v = Verdict(5, "BTS CSV without filters includes unclassified saved candidates", "one download", "")
    rcfg, _ = load_config("configs/replay/replay.yaml")
    bts = BTSCatalog(cache)
    df = bts.load(str(rcfg["bts_snapshot_date"]))
    n_uncl = int((~df["classified"]).sum())
    y25 = df[[m is not None and 60676.0 <= m < 61041.0 for m in df["peak_mjd"]]]
    v.evidence += [
        f"snapshot {rcfg['bts_snapshot_date']}: {len(df)} rows, {n_uncl} unclassified (type '-'); columns {list(df.columns[:17])}",
        f"2025 peaks: {len(y25)} rows, {int((~y25['classified']).sum())} unclassified; "
        f"top types {Counter(y25['type']).most_common(5)}",
        "CSV has savedate/discdate but no classification date (as documented in §2.2).",
    ]
    v.verdict = "PASS" if n_uncl > 0 else "FAIL"
    v.needs_fable = n_uncl == 0
    v.fallback = "" if n_uncl else "redefine unknown bucket (requires Fable decision, §14.7)"
    return v


def kt6_context(cache: Cache) -> Verdict:
    v = Verdict(6, "Lasair token + Sherlock available; SIMBAD/NED rate limits tolerable with caching", "smoke tests", "")
    ok = True
    try:
        las = LasairClient(cache)
        sh = las.sherlock_object(PROBE_SN)
        v.evidence.append(
            f"Lasair Sherlock ({PROBE_SN}): {[(r.get('classification'), r.get('catalogue_object_id'), r.get('z'), r.get('separationArcsec')) for r in sh]}"
        )
        pos = las.sherlock(PROBE_SN_RA, PROBE_SN_DEC)
        v.evidence.append(f"Lasair Sherlock position endpoint keys: {sorted(pos)[:8] if isinstance(pos, dict) else type(pos).__name__}")
        ok &= bool(sh)
    except CredentialMissing as exc:
        v.verdict, v.credential, v.setup = "BLOCKED: CREDENTIAL REQUIRED", exc.name, exc.how
        return v
    except Exception as exc:
        ok = False
        v.evidence.append(f"Lasair Sherlock failed: {type(exc).__name__}: {exc}")
    rng = random.Random(6)
    for name, client in (("SIMBAD", SimbadClient(cache)), ("NED", NedClient(cache))):
        lat, errs, nrows = [], 0, 0
        for _ in range(10):
            ra, dec = rng.uniform(150, 220), rng.uniform(0, 50)
            t0 = time.time()
            try:
                nrows += len(client.cone(ra, dec, 30.0))
            except Exception as exc:
                errs += 1
                v.evidence.append(f"{name} error: {type(exc).__name__}: {str(exc)[:120]}")
            lat.append(time.time() - t0)
        v.evidence.append(
            f"{name}: 10 cone searches (30\"), errors={errs}, rows={nrows}, median latency {statistics.median(lat):.2f}s "
            f"(paced; cached thereafter)"
        )
        ok &= errs == 0
    v.verdict = "PASS" if ok else "FAIL"
    v.fallback = "" if ok else "drop/replace failing tool (M2)"
    return v


def kt7_models(cache: Cache) -> Verdict:
    v = Verdict(7, "Jev and Claude keys; Jev call ~200 ms with ~500-token state", "one call each", "")
    missing = [n for n in ("ANTHROPIC_API_KEY",) if not settings.get_secret(n)]
    if not (settings.get_secret("TYPESAFE_API_KEY") or settings.get_secret("OPENROUTER_API_KEY")):
        missing.append("TYPESAFE_API_KEY (or OPENROUTER_API_KEY)")
    if missing:
        v.verdict = "BLOCKED: CREDENTIAL REQUIRED"
        v.credential = ", ".join(missing)
        v.setup = (
            "ANTHROPIC_API_KEY: create at https://console.anthropic.com -> API keys. "
            "TYPESAFE_API_KEY: create at https://docs.typesafe.ai (quickstart) or use OPENROUTER_API_KEY "
            "(https://openrouter.ai/keys). Add to .env. Live calls are paid: the owner must also approve a spend budget."
        )
        v.evidence.append("No model call attempted (keys absent; and no spend budget approved by the owner).")
    else:
        v.verdict = "BLOCKED: SPEND APPROVAL REQUIRED"
        v.evidence.append("Keys present, but the owner has not approved a model spend budget; no paid call made.")
    v.fallback = "M4 slips; architecture unaffected (§11)"
    return v


def kt8_btsbot(cache: Cache) -> Verdict:
    v = Verdict(8, "btsbot installs and runs on ALeRCE stamps", "inference on 10 alerts", "")
    res_path = OUT / "kt8_btsbot.json"
    if res_path.exists():
        res = json.loads(res_path.read_text())
        v.verdict = res["verdict"]
        v.evidence = res["evidence"]
    else:
        v.verdict = "PARTIAL"
        v.evidence.append("Not run: execute scripts/kt8_btsbot.py (isolated venv; heavy torch install).")
    v.fallback = "multimodal baseline becomes ALeRCE stamp classifier only (M7)" if v.verdict != "PASS" else ""
    return v


def kt9_cpsat(cache: Cache) -> Verdict:
    from ortools.sat.python import cp_model

    v = Verdict(9, "CP-SAT solves 60 targets x 12 h in < 5 s", "toy model", "")
    rng = random.Random(9)
    times = []
    for trial in range(5):
        m = cp_model.CpModel()
        horizon = 12 * 3600 // 60  # minutes
        intervals, presences, objective = [], [], []
        for i in range(60):
            dur = rng.randint(10, 45)  # exposure + 5 min overhead, minutes
            w0 = rng.randint(0, horizon - 120)
            w1 = min(horizon, w0 + rng.randint(120, 480))
            p = m.NewBoolVar(f"p{i}")
            s = m.NewIntVar(w0, w1 - dur, f"s{i}")
            e = m.NewIntVar(w0 + dur, w1, f"e{i}")
            intervals.append(m.NewOptionalIntervalVar(s, dur, e, p, f"iv{i}"))
            presences.append(p)
            objective.append(rng.randint(1, 100) * p)
        m.AddNoOverlap(intervals)
        m.Add(sum(presences) <= 8)
        m.Maximize(sum(objective))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_workers = 8
        solver.parameters.random_seed = trial
        t0 = time.time()
        st = solver.Solve(m)
        times.append(time.time() - t0)
        v.evidence.append(f"trial {trial}: status={solver.StatusName(st)} obj={solver.ObjectiveValue():.0f} "
                          f"bound={solver.BestObjectiveBound():.0f} time={times[-1]:.2f}s")
    v.verdict = "PASS" if max(times) < 5.0 else "FAIL"
    v.fallback = "" if max(times) < 5.0 else "greedy by expected reward"
    return v


def kt10_corpora(cache: Cache) -> Verdict:
    v = Verdict(10, "Corpus ingestion (AstroNotes/ATels/GCN) feasible with dates", "crawl 1 month", "")
    month_lo, month_hi = 60735.0, 60766.0  # 2025-03-01 .. 2025-04-01 (UTC)
    ok = True
    # GCN circulars: ids are sequential; find the month's id range by bisection, then fetch every circular.
    gcn = GcnClient(cache)

    def gdate(i: int) -> float:
        return float(gcn.circular(i)["source_date"])

    def first_at_or_after(mjd: float, lo: int, hi: int) -> int:
        while lo < hi:
            mid = (lo + hi) // 2
            try:
                d = gdate(mid)
            except Exception:
                mid_ok = False
                for k in range(1, 6):
                    try:
                        d = gdate(mid + k)
                        mid += k
                        mid_ok = True
                        break
                    except Exception:
                        continue
                if not mid_ok:
                    lo = mid + 1
                    continue
            if d < mjd:
                lo = mid + 1
            else:
                hi = mid
        return lo

    try:
        g0 = first_at_or_after(month_lo, 38500, 41000)
        g1 = first_at_or_after(month_hi, g0, 41500)
        got, bad = 0, 0
        for i in range(g0, g1):
            try:
                c = gcn.circular(i)
                got += int(month_lo <= c["source_date"] < month_hi)
            except Exception:
                bad += 1
        v.evidence.append(f"GCN: circulars {g0}..{g1 - 1}: {got} dated in month, {bad} fetch failures")
        ok &= got > 0
    except Exception as exc:
        ok = False
        v.evidence.append(f"GCN failed: {type(exc).__name__}: {exc}")
    # ATels: sequential numbers; walk the month.
    atel = AtelClient(cache)
    try:
        n, got, undated, first = 17030, 0, 0, None
        while True:
            a = atel.telegram(n)
            if a is None:
                undated += 1
                if undated > 5:
                    break
            else:
                if a["source_date"] >= month_hi:
                    break
                if a["source_date"] >= month_lo:
                    got += 1
                    first = first or n
            n += 1
        v.evidence.append(f"ATel: {got} telegrams dated in month (from #{first} to #{n - 1}); {undated} unparseable; "
                          "'Referred to by' and 'Related' (later telegrams) stripped at parse time")
        ok &= got > 0
    except Exception as exc:
        ok = False
        v.evidence.append(f"ATel failed: {type(exc).__name__}: {exc}")
    # AstroNotes: listing pages newest-first.
    an = AstroNoteClient(cache)
    try:
        page, got, seen_older = 0, 0, False
        while page < 80 and not seen_older:
            notes = an.listing(page)
            if not notes:
                break
            for x in notes:
                if x["id"].startswith("AstroNote2025") and month_lo <= x["source_date"] < month_hi:
                    got += 1
            years = [x["id"][9:13] for x in notes if x["id"][9:13].isdigit()]
            if years and max(years) < "2025":
                seen_older = True
            page += 1
        v.evidence.append(f"AstroNotes: {got} notes with release/last-modified date in month (scanned {page} listing pages); "
                          "date is 'last modified' (may post-date first release) — as-of filter must treat it as an upper bound; "
                          "object tooltips with current TNS type/redshift stripped")
        ok &= got > 0
    except Exception as exc:
        ok = False
        v.evidence.append(f"AstroNotes failed: {type(exc).__name__}: {exc}")
    v.verdict = "PASS" if ok else "PARTIAL"
    v.fallback = "" if ok else "restrict to TNS + catalogs for M2"
    return v


def kt11(cache: Cache) -> Verdict:
    return Verdict(11, "Investigator decision impact may be small on easy candidates", "M3 design", "DEFERRED",
                   ["By architecture this is addressed in M3/M4 design (stratified easy/ambiguous/contaminant Tier-B; "
                    "null results reported honestly). Not testable in M0."],
                   "report null honestly; stratify")


def kt12(cache: Cache) -> Verdict:
    return Verdict(12, "Jev first-option bias / literal reading", "M4", "DEFERRED",
                   ["By architecture measured in M4/M5 (option-order flip test). Also requires TYPESAFE_API_KEY "
                    "and a spend budget (not configured)."],
                   "randomize order, measure flips")


TESTS: dict[int, Callable[[Cache], Verdict]] = {
    1: kt1_tns, 2: kt2_fink, 3: kt3_pool_volume, 4: kt4_budget, 5: kt5_bts, 6: kt6_context, 7: kt7_models,
    8: kt8_btsbot, 9: kt9_cpsat, 10: kt10_corpora, 11: kt11, 12: kt12,
}


def render(vs: list[Verdict]) -> str:
    lines = [
        "# M0 kill-tests (ARCHITECTURE §11)",
        "",
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} by `scripts/m0_killtests.py` "
        f"(code {settings.code_version()}). No paid model calls were made.",
        "",
        "| # | Assumption | Verdict | Fallback / note |",
        "|---|---|---|---|",
    ]
    for v in vs:
        note = v.fallback + (" **Needs Fable decision.**" if v.needs_fable else "")
        lines.append(f"| {v.id} | {v.assumption} | **{v.verdict}** | {note} |")
    lines.append("")
    go = all(v.verdict in ("PASS", "DEFERRED") for v in vs if v.id <= 5)
    lines += [
        "## Go / no-go",
        "",
        ("**GO for M1** on the data spine: #2–#5 pass. " if go else "**Partial GO:** ")
        + "Blocked items do not block M1 (candidate spine); #1 (TNS) gates M2's prior-classification tool and "
        "Tier-A truth, #7 gates M2 extraction and all Jev roles.",
        "",
        "## Evidence",
        "",
    ]
    for v in vs:
        lines.append(f"### {v.id}. {v.assumption}")
        lines.append(f"*Test:* {v.test} · *Verdict:* **{v.verdict}** · {v.seconds:.1f}s")
        if v.credential:
            lines.append(f"- **Credential:** `{v.credential}`")
            lines.append(f"- **Setup:** {v.setup}")
        lines += [f"- {e}" for e in v.evidence]
        if v.fallback:
            lines.append(f"- *Fallback:* {v.fallback}" + (" — **requires Fable decision (§14.7)**" if v.needs_fable else ""))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    OUT.mkdir(parents=True, exist_ok=True)
    cache = Cache()
    ids = [int(x) for x in args.only.split(",") if x] or sorted(TESTS)
    prev: dict[int, dict[str, Any]] = {}
    jpath = OUT / "killtests.json"
    if jpath.exists():
        prev = {d["id"]: d for d in json.loads(jpath.read_text())}
    results: dict[int, Verdict] = {i: Verdict(**d) for i, d in prev.items()}
    for i in ids:
        t0 = time.time()
        try:
            v = TESTS[i](cache)
        except Exception as exc:
            v = Verdict(i, TESTS[i].__name__, "", "ERROR", [f"{type(exc).__name__}: {exc}", traceback.format_exc()[-800:]])
        v.seconds = time.time() - t0
        results[i] = v
        print(f"#{i:>2} {v.verdict:<32} {v.assumption}", flush=True)
    vs = [results[i] for i in sorted(results)]
    jpath.write_text(json.dumps([asdict(v) for v in vs], indent=1))
    (OUT / "killtests.md").write_text(render(vs))
    print(f"wrote {OUT / 'killtests.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
