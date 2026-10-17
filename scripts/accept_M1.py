"""M1 acceptance (ARCHITECTURE §10.3 M1, §13.5): prints PASS/FAIL per criterion; writes runs/m1/accept.json.

Completion criteria (§10.3 M1):
  C1 Snapshot(t) for 5 consecutive nights builds from cache in < 60 s (fresh process, COSMIC_OFFLINE=1)
  C2 >= 20 leakage fixtures pass, incl. detection at t+0.01 d, Fink row jd > t, BTS `type`, final `ndethist`
  C3 pool-size and bright-candidate counts per night in runs/m1/pool_stats.md with the budget-binding check (§6.3)
  C4 console renders any pool candidate at any t (API serves every pool candidate of every night + frames;
     console type-checks and builds)
Deliverables also checked: Snapshot-only import rules (§13.2) with tests, deterministic replay output hash on
re-run, Night Theater S0 frames at 5-min cadence via /theater/*, vertical-slice OID recorded, full offline suite.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cosmic_triage.settings import PROJECT_ROOT, load_config

R = PROJECT_ROOT
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def run(cmd: list[str], env: dict[str, str] | None = None, cwd: Path = R, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=timeout)


SNAP_TIMER = r"""
import os, time, json
os.environ["COSMIC_OFFLINE"] = "1"
t0 = time.time()
from cosmic_triage.ingest import AlerceClient, Cache, FinkClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.replay.clock import Clock
from cosmic_triage.replay.pool import ForwardPool, night_t
from cosmic_triage.settings import load_config
rcfg, _ = load_config("configs/replay/replay.yaml")
c = Cache(offline=True)
pool = ForwardPool(AlerceClient(c), FinkClient(c), AlerceDBClient(c))
clock = Clock()
sizes = {}
for n in rcfg["m1_nights"]:
    s = clock.snapshot(night_t(n, float(rcfg["decision_time_utc_hour"])), pool)
    sizes[n] = len(s.candidates)
print(json.dumps({"seconds": time.time() - t0, "sizes": sizes}))
"""


def main() -> int:
    py = sys.executable
    rcfg, _ = load_config("configs/replay/replay.yaml")
    nights = list(rcfg["m1_nights"])

    # C1 snapshot build time from cache, offline, fresh process
    p = run([py, "-c", SNAP_TIMER], {"COSMIC_OFFLINE": "1"})
    if p.returncode == 0:
        r = json.loads(p.stdout.strip().splitlines()[-1])
        check("C1 Snapshot(t) for 5 consecutive nights from cache < 60 s (offline)", r["seconds"] < 60 and len(r["sizes"]) == 5,
              f"{r['seconds']:.1f}s; pool sizes {r['sizes']}")
    else:
        check("C1 Snapshot(t) for 5 consecutive nights from cache < 60 s (offline)", False, p.stderr[-600:])

    # C2 leakage fixtures
    fx = sorted((R / "tests" / "leakage" / "fixtures").glob("*.json"))
    names = {json.loads(f.read_text())["name"] for f in fx}
    required = {"detection_t_plus_0p01d", "fink_row_jd_after_t", "bts_type_field", "ndethist_final_history"}
    p = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/leakage"], {"COSMIC_OFFLINE": "1"})
    check("C2 >= 20 leakage fixtures pass incl. the four named in §10.3", p.returncode == 0 and len(fx) >= 20 and required <= names,
          f"{len(fx)} fixtures; {p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:]}")

    # C3 pool stats + budget binding
    ps = R / "runs" / "m1" / "pool_stats.json"
    if ps.exists():
        st = json.loads(ps.read_text())
        ok = len(st["nights"]) == 5 and all("pool" in n and "bright_le_18p5_at_t" in n for n in st["nights"]) \
            and (R / "runs" / "m1" / "pool_stats.md").exists() and "Budget-binding" in (R / "runs" / "m1" / "pool_stats.md").read_text()
        check("C3 pool-size + bright counts per night with budget-binding check (runs/m1/pool_stats.md)", ok,
              f"pools {[n['pool'] for n in st['nights']]}; bright SN-like {[n['bright_sn_like'] for n in st['nights']]}; "
              f"largest binding budget {st['budget_max_binding']}")
        check("C3 budget binds at >= 3 spectra/night (else §14.7 decision)", st["budget_max_binding"] >= 3,
              f"B_max={st['budget_max_binding']}")
    else:
        check("C3 pool-size + bright counts per night with budget-binding check (runs/m1/pool_stats.md)", False, "missing")

    # Replay spine artifacts + determinism (run twice offline; identical output hash)
    hashes = []
    run_id = None
    for _ in range(2):
        p = run([py, "scripts/run_m1_spine.py", "--offline"], {"COSMIC_OFFLINE": "1"})
        if p.returncode != 0:
            hashes.append(f"error: {p.stderr[-300:]}")
            continue
        kv = dict(ln.split("=", 1) for ln in p.stdout.splitlines() if "=" in ln and ln.split("=", 1)[0] in ("run_id", "output_hash"))
        hashes.append(kv.get("output_hash", "?"))
        run_id = kv.get("run_id")
    check("D replay spine deterministic: identical output hash on re-run", len(set(hashes)) == 1 and not hashes[0].startswith("error"),
          f"{hashes[0][:16]}… (run {run_id})")

    # C4 console: API serves every candidate of every night + theater frames; console type-checks and builds
    from fastapi.testclient import TestClient

    from cosmic_triage.api.app import app

    c = TestClient(app)
    runs_ = {r["run_id"]: r for r in c.get("/api/runs").json()}
    served, missing, frames_ok = 0, [], True
    if run_id in runs_:
        for night in nights:
            pool = c.get(f"/api/runs/{run_id}/nights/{night}/candidates").json()
            for cand in pool["candidates"]:
                rr = c.get(f"/api/runs/{run_id}/nights/{night}/candidates/{cand['oid']}")
                if rr.status_code == 200 and rr.json()["candidate"]["photometry"]:
                    served += 1
                else:
                    missing.append((night, cand["oid"]))
            fr = c.get(f"/theater/{run_id}/{night}/frames").json()
            ts = [f["t_mjd"] for f in fr["frames"]]
            steps = {round((b - a) * 1440, 3) for a, b in itertools.pairwise(ts)}
            frames_ok &= steps == {5.0} and fr["header"]["n_candidates"] == len(pool["candidates"])
    check("C4 API serves every pool candidate (light curve) for every night", run_id in runs_ and not missing,
          f"{served} candidate-nights served; missing {missing[:3]}")
    check("D Night Theater S0 frames at 5-min cadence for every night via /theater/*", run_id in runs_ and frames_ok)
    console = R / "console"
    if (console / "node_modules").exists():
        p = run(["npm", "run", "build"], cwd=console, timeout=600)
        check("C4 console type-checks and builds (tsc + vite)", p.returncode == 0,
              (p.stdout + p.stderr).strip().splitlines()[-1] if (p.stdout + p.stderr).strip() else "")
    else:
        check("C4 console type-checks and builds (tsc + vite)", False, "run `cd console && npm install` first")

    # Deliverables
    li = str(Path(py).parent / "lint-imports")
    p = run([li])
    check("D Snapshot-only access: import-linter contracts kept", p.returncode == 0 and "0 broken" in p.stdout)
    p = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/unit/test_import_boundaries.py"], {"COSMIC_OFFLINE": "1"})
    check("D Snapshot-only access: boundary tests incl. injected-violation test", p.returncode == 0, p.stdout.strip().splitlines()[-1])
    vs = R / "runs" / "m1" / "vertical_slice.json"
    chosen = json.loads(vs.read_text()).get("chosen") if vs.exists() else None
    check("D vertical-slice object identified (BTS SN Ia 2025 + Sherlock host + TNS class)", bool(chosen),
          chosen["oid"] if chosen else "not found (documented in M1 report)")
    p = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], {"COSMIC_OFFLINE": "1"})
    check("D full test suite green offline", p.returncode == 0, p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:])
    p = run([py, "-m", "ruff", "check", "."])
    check("D ruff clean", p.returncode == 0)
    p = run([py, "-m", "mypy", "src/cosmic_triage/contracts", "src/cosmic_triage/investigator"])
    check("D mypy --strict on contracts + investigator", p.returncode == 0, p.stdout.strip().splitlines()[-1])

    ok = all(r[1] for r in results)
    (R / "runs" / "m1" / "accept.json").write_text(
        json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "checks": [{"criterion": n, "pass": o, "detail": d} for n, o, d in results]}, indent=1))
    print(f"\nM1 acceptance: {'PASS' if ok else 'FAIL'} ({sum(r[1] for r in results)}/{len(results)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
