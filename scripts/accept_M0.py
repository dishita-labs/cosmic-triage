"""M0 acceptance (ARCHITECTURE §10.3, §13.5): prints PASS/FAIL per completion criterion; writes runs/m0/accept.json.

Criteria (§10.3 M0):
  C1 all 12 kill-tests have a recorded verdict; failures of #1-#5 carry a fallback flagged for Fable (§14.7)
  C2 every contract round-trips JSON via model_validate(model_dump())
  C3 `uv run pytest` green with no network (COSMIC_OFFLINE=1)
Deliverables checked alongside: scaffold layout (§9), recorded fixtures for every external API touched,
.env.example (names only) with .env git-ignored, pre-commit (ruff), mypy --strict, import-linter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cosmic_triage.settings import PROJECT_ROOT

R = PROJECT_ROOT
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def run(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=R, capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=1800)


def main() -> int:
    # C1 kill-tests
    kp = R / "runs" / "m0" / "killtests.json"
    if kp.exists():
        kts = {d["id"]: d for d in json.loads(kp.read_text())}
        recorded = all(i in kts and kts[i]["verdict"] not in ("", "ERROR") for i in range(1, 13))
        fails_flagged = all(
            kts[i]["needs_fable"] and kts[i]["fallback"]
            for i in range(1, 6) if i in kts and kts[i]["verdict"] in ("FAIL", "PARTIAL")
        )
        summary = ", ".join(f"#{i}:{kts[i]['verdict']}" for i in sorted(kts))
        check("C1 all 12 kill-tests have a recorded verdict", recorded, summary)
        check("C1 failed #1-#5 carry a fallback flagged for Fable", fails_flagged)
        blocked = [i for i in sorted(kts) if kts[i]["verdict"].startswith("BLOCKED")]
        if blocked:
            print(f"       note: BLOCKED (credential/spend) kill-tests: {blocked} — recorded, NOT passed")
        check("C1 runs/m0/killtests.md written", (R / "runs" / "m0" / "killtests.md").exists())
    else:
        check("C1 all 12 kill-tests have a recorded verdict", False, "runs/m0/killtests.json missing")

    # C2 contracts round-trip
    p = run([sys.executable, "-m", "pytest", "-q", "tests/contracts"], {"COSMIC_OFFLINE": "1"})
    check("C2 every contract round-trips JSON (tests/contracts)", p.returncode == 0, p.stdout.strip().splitlines()[-1])

    # C3 full suite offline
    p = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], {"COSMIC_OFFLINE": "1"})
    last = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-300:]
    check("C3 uv run pytest green with COSMIC_OFFLINE=1 (sockets blocked)", p.returncode == 0, last)

    # Deliverables
    layout = [
        "src/cosmic_triage/contracts", "src/cosmic_triage/ingest", "src/cosmic_triage/belief", "src/cosmic_triage/value",
        "src/cosmic_triage/schedule", "src/cosmic_triage/replay", "src/cosmic_triage/investigator",
        "src/cosmic_triage/metrics", "src/cosmic_triage/api",
        *[f"src/cosmic_triage/investigator/{d}" for d in ("tools", "orchestrator", "ledger", "validators", "extractors", "routers")],
        *[f"configs/{d}" for d in ("objectives", "facilities", "policies", "investigator")],
        "data/cache", "runs", "docs", "tests/unit", "tests/leakage", "tests/fixtures",
    ]
    missing = [d for d in layout if not (R / d).is_dir()]
    check("D scaffold layout (§9)", not missing, f"missing: {missing}" if missing else f"{len(layout)} dirs")
    from cosmic_triage import contracts as C

    names = ["PhotometryPoint", "CandidateContext", "CandidateState", "Snapshot", "Belief", "Objective", "RewardTable",
             "Action", "Schedule", "Outcome", "Evidence", "Claim", "ClaimDraft", "ValidationReport", "EvidenceLedger",
             "Span", "Trace", "DecisionTrace", "Label", "RunConfig", "NightFrame", "Compaction"]
    absent = [n for n in names if not hasattr(C, n)]
    check("D contracts package has every type in §3/§4.3/§13.3", not absent, f"absent: {absent}" if absent else "")
    fx = R / "tests" / "fixtures" / "cache"
    apis = ["alerce", "fink", "lasair", "bts", "simbad", "ned", "gcn", "atel", "astronote"]
    nofx = [a for a in apis if not any((fx / a).rglob("*.json"))]
    check("D recorded fixtures for every external API touched", not nofx,
          f"missing {nofx}" if nofx else f"{apis} (TNS: not touched — credential blocked)")
    envx = (R / ".env.example").read_text() if (R / ".env.example").exists() else ""
    vals = [ln for ln in envx.splitlines() if ln and not ln.startswith("#") and ln.split("=", 1)[1].strip()]
    check("D .env.example present with names only", bool(envx) and not vals)
    ig = run(["git", "check-ignore", "-q", ".env"])
    tracked = run(["git", "ls-files", "--error-unmatch", ".env"])
    check("D .env is git-ignored and untracked", ig.returncode == 0 and tracked.returncode != 0)
    check("D pre-commit config (ruff)", "ruff" in (R / ".pre-commit-config.yaml").read_text())
    p = run([sys.executable, "-m", "ruff", "check", "."])
    check("D ruff clean", p.returncode == 0, p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "")
    p = run([sys.executable, "-m", "mypy", "src/cosmic_triage/contracts", "src/cosmic_triage/investigator"])
    check("D mypy --strict on contracts + investigator", p.returncode == 0, p.stdout.strip().splitlines()[-1])
    li = str(Path(sys.executable).parent / "lint-imports")
    p = run([li])
    check("D import-linter contracts kept", p.returncode == 0, [ln for ln in p.stdout.splitlines() if "kept" in ln][-1:][0]
          if p.stdout else p.stderr[-200:])

    ok = all(r[1] for r in results)
    out = R / "runs" / "m0" / "accept.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([{"criterion": n, "pass": o, "detail": d} for n, o, d in results], indent=1))
    print(f"\nM0 acceptance: {'PASS' if ok else 'FAIL'} ({sum(r[1] for r in results)}/{len(results)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
