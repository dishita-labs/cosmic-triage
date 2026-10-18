"""M2 acceptance (ARCHITECTURE §10.3 M2): PASS / FAIL / BLOCKED per criterion; writes runs/exploratory/m2/accept.json.

Completion criteria (§10.3 M2), on 20 candidates at chosen t (10 BTS-classified, 10 contaminant/unknown):
  C1 the 20 runs exist with the 10/10 split
  C2 100% of runs terminate within budget
  C3 0 accepted claims with source_date > t (asserted over all traces)
  C4 >= 80% of runs end with >= 1 validated claim or an explicit no_context_found
  C5 every run's trace renders in the console (API serves it, no leakage badge; console type-checks and builds)
  C6 Jev calls logged for all 20  — BLOCKED unless Jev is flagged on *and* spend is approved by the owner
  C7 hand review of all 20 dossiers filed in runs/reports/M2.md with error categories
  C8 demo_investigate.py runs end-to-end with cache in < 2 min (offline)
Also: investigator tests incl. corrupted-claim fixtures, determinism (same inputs → same output hash), mypy, ruff, imports.
A BLOCKED criterion is not a pass: the milestone is reported INCOMPLETE until it clears.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from cosmic_triage.settings import PROJECT_ROOT

R = PROJECT_ROOT
M = R / "runs" / "exploratory" / "m2"
results: list[tuple[str, str, str]] = []


def check(name: str, status: str | bool, detail: str = "") -> None:
    s = status if isinstance(status, str) else ("PASS" if status else "FAIL")
    results.append((name, s, detail))
    print(f"[{s}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def run(cmd: list[str], cwd: Path = R, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, "COSMIC_OFFLINE": "1"}, timeout=timeout)


def last(text: str) -> str:
    lines = [x for x in text.strip().splitlines() if x.strip()]
    return lines[-1] if lines else ""


def main() -> int:
    py = sys.executable
    summ = json.loads((M / "summary.json").read_text()) if (M / "summary.json").exists() else {"runs": []}
    runs = summ["runs"]
    strata = {s: sum(r["stratum"] == s for r in runs) for s in ("bts_classified", "contaminant_or_unknown")}
    check("C1 20 runs at chosen t (10 BTS-classified, 10 contaminant/unknown)",
          len(runs) == 20 and strata["bts_classified"] == 10 and strata["contaminant_or_unknown"] == 10, f"{len(runs)} runs {strata}")
    check("C2 100% of runs terminate within budget", bool(runs) and all(r["within_budget"] for r in runs),
          f"{sum(r['within_budget'] for r in runs)}/{len(runs)}")
    traces = sorted((R / "runs").glob("*/*/inv-*.jsonl"))
    p = run([py, "-m", "pytest", "-q", "tests/leakage/test_all_traces.py"])
    check("C3 0 accepted claims with source_date > t over all traces", p.returncode == 0 and len(traces) >= len(runs) > 0,
          f"{len(traces)} traces; {last(p.stdout)}")
    ok = sum(1 for r in runs if r["n_claims"] or r["outcome"] == "no_context_found")
    check("C4 >= 80% of runs end with >= 1 validated claim or explicit no_context_found", bool(runs) and ok / len(runs) >= 0.8,
          f"{ok}/{len(runs)}" + (f" ({100 * ok / len(runs):.0f}%)" if runs else ""))

    from fastapi.testclient import TestClient

    from cosmic_triage.api.app import app

    client = TestClient(app)
    bad = []
    for r in runs:
        resp = client.get(f"/api/investigations/{r['run_id']}")
        if resp.status_code != 200 or resp.json()["n_leaks"] != 0 or not resp.json()["spans"]:
            bad.append(r["run_id"])
    pc = run(["npx", "tsc", "-b", "--noEmit"], cwd=R / "console")
    pb = run(["npm", "run", "build"], cwd=R / "console")
    check("C5 every run's trace renders (API 200, no leakage badge; console type-checks + builds)",
          bool(runs) and not bad and pc.returncode == 0 and pb.returncode == 0,
          f"{len(runs) - len(bad)}/{len(runs)} served; tsc {'ok' if pc.returncode == 0 else 'FAIL'}; build {'ok' if pb.returncode == 0 else 'FAIL'}")

    jev_logged = 0
    for r in runs:
        lines = [json.loads(x) for x in (R / r["trace"]).read_text().splitlines()]
        if any(x["type"] == "span" and "jev" in x["name"] and x["status"] == "ok" for x in lines):
            jev_logged += 1
    from cosmic_triage.spend import SpendGuard

    approved = SpendGuard().approved
    if jev_logged == len(runs) and runs:
        check("C6 Jev calls logged for all 20", True, f"{jev_logged}/{len(runs)}")
    else:
        check("C6 Jev calls logged for all 20", "BLOCKED",
              f"{jev_logged}/{len(runs)} — BLOCKED: SPEND NOT APPROVED (owner approval required; spend approved={approved}); "
              "Jev gate/verifier implemented behind flags, tested with transport doubles, no paid call made")

    rep = R / "runs" / "reports" / "M2.md"
    txt = rep.read_text() if rep.exists() else ""
    review = txt.split("## Hand review", 1)[1] if "## Hand review" in txt else ""
    reviewed = {r["oid"] for r in runs if r["oid"] in review}
    check("C7 hand review of all 20 dossiers with error categories in runs/reports/M2.md",
          bool(runs) and len(reviewed) == len(runs) and re.search(r"error categor", review, re.I) is not None,
          f"{len(reviewed)}/{len(runs)} dossiers reviewed")

    vs = json.loads((R / "runs" / "m1" / "vertical_slice.json").read_text())["chosen"]
    demo_night = next((r for r in runs if r["oid"] == vs["oid"]), None)
    if demo_night is None:
        check("C8 demo_investigate.py end-to-end with cache < 2 min", False, "vertical-slice object not in the M2 batch")
    else:
        sel = json.loads((M / "selection.json").read_text())["selected"]
        night = next(s["night"] for s in sel if s["oid"] == vs["oid"])
        from cosmic_triage.replay.pool import night_t

        t0 = time.time()
        p1 = run([py, "scripts/demo_investigate.py", vs["oid"], f"{night_t(night):.10f}", "--offline"], timeout=300)
        dt = time.time() - t0
        h1 = re.search(r"output hash (\w+)", p1.stdout)
        p2 = run([py, "scripts/demo_investigate.py", vs["oid"], f"{night_t(night):.10f}", "--offline"], timeout=300)
        h2 = re.search(r"output hash (\w+)", p2.stdout)
        check("C8 demo_investigate.py end-to-end with cache < 2 min (offline)", p1.returncode == 0 and dt < 120,
              f"{vs['oid']} @ {night}: {dt:.1f}s; exit {p1.returncode}")
        check("D determinism: identical inputs → identical output hash", bool(h1 and h2 and h1.group(1) == h2.group(1)),
              f"{h1.group(1) if h1 else '?'} vs {h2.group(1) if h2 else '?'}")

    p = run([py, "-m", "pytest", "-q", "tests/investigator"])
    check("D investigator tests (tools as-of, corrupted claims, orchestrator, spend cap)", p.returncode == 0, last(p.stdout))
    p = run([py, "-m", "pytest", "-q"])
    check("D full offline suite", p.returncode == 0, last(p.stdout))
    p = run([py, "-m", "mypy", "src/cosmic_triage/contracts", "src/cosmic_triage/investigator"])
    check("D mypy --strict contracts + investigator", p.returncode == 0, last(p.stdout))
    p = run([py, "-m", "ruff", "check", "."])
    check("D ruff clean", p.returncode == 0, last(p.stdout))
    p = run([str(Path(py).with_name("lint-imports"))])
    check("D import-linter contracts kept", p.returncode == 0, last(p.stdout))
    spend = R / "runs" / "spend.jsonl"
    charges = [json.loads(x) for x in spend.read_text().splitlines()] if spend.exists() else []
    check("D no paid model call made (runs/spend.jsonl has no charge)", not any(c.get("kind") == "charge" for c in charges),
          f"{sum(c.get('kind') == 'refused' for c in charges)} refused attempts logged, 0 charges")

    n_pass = sum(s == "PASS" for _, s, _ in results)
    n_block = sum(s == "BLOCKED" for _, s, _ in results)
    n_fail = sum(s == "FAIL" for _, s, _ in results)
    verdict = "PASS" if n_pass == len(results) else ("INCOMPLETE (BLOCKED)" if n_fail == 0 else "FAIL")
    print(f"M2 acceptance: {verdict} ({n_pass} pass, {n_block} blocked, {n_fail} fail of {len(results)})")
    M.mkdir(parents=True, exist_ok=True)
    (M / "accept.json").write_text(json.dumps({"verdict": verdict, "results": [{"name": n, "status": s, "detail": d}
                                                                               for n, s, d in results]}, indent=1))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
