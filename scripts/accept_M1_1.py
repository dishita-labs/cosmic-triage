"""M1.1 acceptance (ARCHITECTURE §10.3 M1.1): prints PASS/FAIL per criterion; writes runs/m1/m1.1/accept.json.

Completion criteria (§10.3 M1.1):
  C1 new leakage fixtures pass: (i) prv detection delivered by an alert with jd > t excluded; (ii) non-detection older
     than any delivering alert excluded; (iii) alert-time i:jdstarthist before the window -> first_detection_before_window;
     (iv) Fink row jd > t with an earlier i:jdstarthist ignored; (v) object-level jdstarthist/ndethist injected into
     ALeRCE records scrubbed
  C2 pool stats regenerated with contaminant counts before/after
  C3 bright-regime recall >= 95% or each miss explained
  C4 labels audit filed (form + links for >= 30 contaminants; the owner does the looking)
  C5 spine output hash changes recorded
Deliverables also checked: second and third vertical-slice objects; full offline suite; ruff; mypy; import rules.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cosmic_triage.settings import PROJECT_ROOT

R = PROJECT_ROOT
M = R / "runs" / "m1" / "m1.1"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=R, capture_output=True, text=True, env={**os.environ, "COSMIC_OFFLINE": "1"}, timeout=1800)


def last(text: str) -> str:
    lines = [x for x in text.strip().splitlines() if x.strip()]
    return lines[-1] if lines else ""


def main() -> int:
    py = sys.executable
    req = ["prv_delivered_after_t", "nondet_older_than_any_delivering_alert", "alert_jdstarthist_before_window",
           "fink_row_after_t_with_old_jdstarthist", "object_level_hist_in_alerce"]
    fx = {json.loads(p.read_text())["name"]: p.stem for p in (R / "tests" / "leakage" / "fixtures").glob("*.json")}
    missing = [r for r in req if r not in fx]
    p = run([py, "-m", "pytest", "-q", "tests/leakage/test_leakage_fixtures.py", "-k",
             " or ".join(fx[r] for r in req if r in fx) + " or required_m1_1"])
    check("C1 M1.1 leakage fixtures (i)-(v) present and pass", not missing and p.returncode == 0,
          f"missing {missing}" if missing else last(p.stdout))
    p = run([py, "-m", "pytest", "-q", "tests/leakage"])
    n_fx = len(fx)
    check("C1 all leakage fixtures pass (M1 + M1.1)", p.returncode == 0, f"{n_fx} fixtures; {last(p.stdout)}")

    ps = json.loads((R / "runs" / "m1" / "pool_stats.json").read_text()) if (R / "runs" / "m1" / "pool_stats.json").exists() else {}
    nights = ps.get("nights", [])
    ok = bool(nights) and all(n.get("before_contaminant") is not None for n in nights)
    regen = ps.get("prefilter_hash") != "9f64125e3daf437c"
    check("C2 pool stats regenerated (pre-filter v1.1) with contaminant counts before/after", ok and regen,
          "; ".join(f"{n['night']}: contaminant {n['before_contaminant']}→{n['labels'].get('contaminant', 0)}" for n in nights)
          or "runs/m1/pool_stats.json missing")

    rb = json.loads((M / "recall_bright.json").read_text()) if (M / "recall_bright.json").exists() else None
    if rb is None:
        check("C3 bright-regime recall >= 95% or each miss explained", False, "runs/m1/m1.1/recall_bright.json missing")
    else:
        unexplained = [m for m in rb["misses"] if not m.get("reasons") or any("unexplained" in r for r in m["reasons"])]
        notes = M / "recall_miss_notes.json"
        explained_by_note = json.loads(notes.read_text()) if notes.exists() else {}
        still = [m for m in unexplained if m["oid"] not in explained_by_note]
        rec = rb["recall"] or 0.0
        check("C3 bright-regime recall >= 95% or each miss explained", rec >= 0.95 or not still,
              f"recall {100 * rec:.1f}% ({rb['total_reached']}/{rb['total_denominator']}); {len(rb['misses'])} miss object-nights, "
              f"{len(still)} unexplained")

    audit = R / "runs" / "reports" / "labels_audit.md"
    form = M / "labels_audit_form.csv"
    rows = form.read_text().splitlines()[1:] if form.exists() else []
    text = audit.read_text() if audit.exists() else ""
    check("C4 labels audit filed with form + links for >= 30 contaminants (owner judgements pending)",
          audit.exists() and len(rows) >= 30 and "alerce.online/object" in text and "AWAITING OWNER REVIEW" in text,
          f"{len(rows)} sampled objects; judgements: pending owner (by design)")

    rep = R / "runs" / "reports" / "M1.1.md"
    rtext = rep.read_text() if rep.exists() else ""
    check("C5 spine output hash change recorded", "ef006c81" in rtext and "output hash" in rtext.lower(),
          "runs/reports/M1.1.md" if rep.exists() else "runs/reports/M1.1.md missing")

    vs = json.loads((M / "vertical_slices.json").read_text()) if (M / "vertical_slices.json").exists() else {}
    a, b = (vs.get("already_classified_sn") or {}).get("chosen"), (vs.get("agn_contaminant") or {}).get("chosen")
    check("D second and third vertical-slice objects recorded", bool(a and b),
          f"classified-at-t: {a and a['oid']}; AGN contaminant: {b and b['oid']}")

    p = run([py, "-m", "pytest", "-q"])
    check("D full offline suite (COSMIC_OFFLINE=1, sockets blocked)", p.returncode == 0, last(p.stdout))
    p = run([py, "-m", "ruff", "check", "."])
    check("D ruff clean", p.returncode == 0, last(p.stdout))
    p = run([py, "-m", "mypy", "src/cosmic_triage/contracts", "src/cosmic_triage/investigator"])
    check("D mypy --strict contracts + investigator", p.returncode == 0, last(p.stdout))
    p = run([str(Path(py).with_name("lint-imports"))])
    check("D import-linter contracts kept", p.returncode == 0, last(p.stdout))

    n_ok = sum(ok for _, ok, _ in results)
    verdict = "PASS" if n_ok == len(results) else "FAIL"
    print(f"M1.1 acceptance: {verdict} ({n_ok}/{len(results)})")
    M.mkdir(parents=True, exist_ok=True)
    (M / "accept.json").write_text(json.dumps({"verdict": verdict, "results": [{"name": n, "pass": o, "detail": d} for n, o, d in results]},
                                              indent=1))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
