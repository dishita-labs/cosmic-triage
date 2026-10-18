"""Console API (ARCHITECTURE §3.2, §8): presentation only. Serves replay artifacts from runs/; no science here.

Run: uv run uvicorn cosmic_triage.api.app:app --reload
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from cosmic_triage.contracts import CandidateState, RunManifest, Snapshot, TheaterNight
from cosmic_triage.settings import PROJECT_ROOT

RUNS = Path(os.environ.get("COSMIC_RUNS_DIR", PROJECT_ROOT / "runs"))

app = FastAPI(title="Cosmic Triage console API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def _run_dirs() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for mode in ("bench", "exploratory"):
        for m in sorted((RUNS / mode).glob("*/*/manifest.json")):
            out[m.parent.name] = m.parent
    return out


def _run_dir(run_id: str) -> Path:
    d = _run_dirs().get(run_id)
    if d is None:
        raise HTTPException(404, f"unknown run {run_id}")
    return d


@lru_cache(maxsize=64)
def _load_json(path: str, mtime: float) -> Any:
    return json.loads(Path(path).read_text())


def _json(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(404, f"missing artifact {path.name}")
    return _load_json(str(path), path.stat().st_mtime)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/runs")
def runs() -> list[dict[str, Any]]:
    out = []
    for run_id, d in sorted(_run_dirs().items()):
        m = RunManifest.model_validate(_json(d / "manifest.json"))
        nights = sorted(p.stem for p in (d / "snapshots").glob("*.json"))
        out.append({"run_id": run_id, "mode": m.config.mode, "config_hash": m.config.config_hash, "seed": m.config.seed,
                    "output_hash": m.output_hash, "code_version": m.config.code_version, "nights": nights})
    return out


@app.get("/api/runs/{run_id}/nights/{night}/candidates")
def candidates(run_id: str, night: str) -> dict[str, Any]:
    data: dict[str, Any] = _json(_run_dir(run_id) / "pool" / f"{night}.json")
    return data


@app.get("/api/runs/{run_id}/nights/{night}/candidates/{oid}")
def candidate(run_id: str, night: str, oid: str) -> dict[str, Any]:
    snap = Snapshot.model_validate(_json(_run_dir(run_id) / "snapshots" / f"{night}.json"))
    for c in snap.candidates:
        if c.oid == oid:
            state: CandidateState = c
            return {"t_mjd": snap.t_mjd, "night_id": snap.night_id, "candidate": state.model_dump()}
    raise HTTPException(404, f"{oid} not in the pool for {night}")


@app.get("/theater/nights")
def theater_nights() -> list[dict[str, Any]]:
    out = []
    for run_id, d in sorted(_run_dirs().items()):
        for p in sorted((d / "theater").glob("*.json")):
            h = TheaterNight.model_validate(_json(p)["header"])
            out.append({"run_id": run_id, "night": h.night_id, "mode": h.mode, "config_hash": h.config_hash,
                        "n_candidates": h.n_candidates, "n_frames": h.n_frames})
    return out


@app.get("/theater/{run_id}/{night}/frames")
def theater_frames(run_id: str, night: str) -> dict[str, Any]:
    data: dict[str, Any] = _json(_run_dir(run_id) / "theater" / f"{night}.json")
    return data


@app.get("/theater/{run_id}/{night}/events")
def theater_events(run_id: str, night: str) -> list[dict[str, Any]]:
    """S0 has no timeline events (detections-in-time arrive with S1, Investigator events with S2)."""
    _json(_run_dir(run_id) / "theater" / f"{night}.json")
    return []


# --- Investigator traces (M2): runs/{exploratory|bench}/<night>/<run_id>.jsonl -----------------------------------------
def _trace_files() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for mode in ("exploratory", "bench"):
        for p in sorted((RUNS / mode).glob("*/inv-*.jsonl")):
            out[p.stem] = p
    return out


def _trace(run_id: str) -> list[dict[str, Any]]:
    p = _trace_files().get(run_id)
    if p is None:
        raise HTTPException(404, f"unknown investigation {run_id}")
    lines: list[dict[str, Any]] = _load_jsonl(str(p), p.stat().st_mtime)
    return lines


@lru_cache(maxsize=256)
def _load_jsonl(path: str, mtime: float) -> list[dict[str, Any]]:
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


@app.get("/api/investigations")
def investigations() -> list[dict[str, Any]]:
    out = []
    for run_id in sorted(_trace_files()):
        lines = _trace(run_id)
        head = lines[0]
        out.append({**{k: head[k] for k in ("run_id", "oid", "t_mjd", "night_id", "mode", "outcome", "stop_reason", "cost_usd",
                                            "within_budget")},
                    "label": head.get("label"), "n_claims": sum(1 for x in lines if x["type"] == "claim"),
                    "n_evidence": sum(1 for x in lines if x["type"] == "evidence"),
                    "n_rejected": sum(1 for x in lines if x["type"] == "rejected")})
    return out


@app.get("/api/investigations/{run_id}")
def investigation(run_id: str) -> dict[str, Any]:
    """Trace + ledger. ``leak`` is computed here (source_date > t) so the console only renders the badge."""
    lines = _trace(run_id)
    head = lines[0]
    t = float(head["t_mjd"])
    evidence = []
    for e in (x for x in lines if x["type"] == "evidence"):
        sd = e.get("source_date")
        evidence.append({**e, "dt_days": None if sd is None else round(float(sd) - t, 4),
                         "leak": bool((sd is not None and float(sd) > t) or float(e["retrieved_at_sim_time"]) != t)})
    return {"header": head, "spans": [x for x in lines if x["type"] == "span"], "evidence": evidence,
            "claims": [x for x in lines if x["type"] == "claim"], "rejected": [x for x in lines if x["type"] == "rejected"],
            "n_leaks": sum(1 for e in evidence if e["leak"])}
