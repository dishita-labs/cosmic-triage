"""§13.5 / §10.3 M2: over every Investigator trace on disk, 0 accepted claims cite evidence with source_date > t.

Runs over runs/{exploratory,bench}/*/inv-*.jsonl. A failure is a §14.8 stop condition (leakage assertion failed).
"""

from __future__ import annotations

import json
from pathlib import Path

from cosmic_triage.settings import PROJECT_ROOT

TRACES = sorted((PROJECT_ROOT / "runs").glob("*/*/inv-*.jsonl"))


def check(path: Path) -> list[str]:
    lines = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    t = float(lines[0]["t_mjd"])
    ev = {e["id"]: e for e in lines if e["type"] == "evidence"}
    bad = []
    for e in ev.values():
        if (e["source_date"] is not None and e["source_date"] > t) or e["retrieved_at_sim_time"] != t:
            bad.append(f"{path.name}: evidence {e['id']} dated {e['source_date']} > t={t}")
    for c in (x for x in lines if x["type"] == "claim"):
        assert c["validation"]["accepted"], f"{path.name}: unaccepted claim in ledger"
        for i in c["evidence_ids"]:
            if i not in ev:
                bad.append(f"{path.name}: claim cites missing evidence {i}")
            elif ev[i]["source_date"] is not None and ev[i]["source_date"] > t:
                bad.append(f"{path.name}: accepted {c['kind']} cites {i} dated {ev[i]['source_date']} > t={t}")
        d = c["payload"].get("date_mjd")
        if isinstance(d, int | float) and d > t:
            bad.append(f"{path.name}: accepted {c['kind']} carries date {d} > t")
    return bad


def test_no_accepted_claim_cites_post_t_evidence_in_any_trace() -> None:
    problems = [p for path in TRACES for p in check(path)]
    assert not problems, problems[:10]
