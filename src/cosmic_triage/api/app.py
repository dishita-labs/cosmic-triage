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
