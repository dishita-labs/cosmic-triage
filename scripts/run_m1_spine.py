"""M1 replay spine run: Snapshot(t) + Night Theater S0 frames for the configured nights, from cache.

Deterministic: run_id and every artifact depend only on (configs, seed, nights, cache contents). The manifest
records seed, config hashes, code version, model ids (none in M1), tokens/USD (zero) and the output hash.

Usage: uv run python scripts/run_m1_spine.py [--nights 2025-04-01,...] [--seed 0] [--offline]
Artifacts: runs/bench/<first-night>/<run_id>/ and the span log runs/bench/<first-night>/<run_id>.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from cosmic_triage.contracts import RunConfig, RunManifest, Span
from cosmic_triage.ingest import AlerceClient, Cache, FinkClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.replay.clock import Clock
from cosmic_triage.replay.denylist import Denylist
from cosmic_triage.replay.pool import ForwardPool, PrefilterConfig, night_t
from cosmic_triage.replay.theater import build_night
from cosmic_triage.schedule.visibility import Site
from cosmic_triage.settings import PROJECT_ROOT, code_version, combined_hash, load_config, sha256_hex

CONFIGS = {
    "prefilter": "configs/replay/prefilter.yaml",
    "denylist": "configs/replay/denylist.yaml",
    "replay": "configs/replay/replay.yaml",
    "class_map": "configs/replay/class_map.yaml",
    "facility": "configs/facilities/palomar_sedm.yaml",
}


def write(path: Path, text: str, outputs: dict[str, str], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    outputs[str(path.relative_to(root))] = sha256_hex(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    rcfg, _ = load_config(CONFIGS["replay"])
    ap.add_argument("--nights", default=",".join(rcfg["m1_nights"]))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["COSMIC_OFFLINE"] = "1"
    nights = args.nights.split(",")
    hashes = {k: load_config(v)[1] for k, v in CONFIGS.items()}
    chash = combined_hash(hashes)
    run_id = f"m1spine-{chash[:10]}-s{args.seed}-{nights[0]}-n{len(nights)}"
    root = PROJECT_ROOT / "runs" / "bench" / nights[0]
    rdir = root / run_id
    cache = Cache()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache), cfg=PrefilterConfig.load(),
                       deny=Denylist.load())
    clock = Clock(pool.deny, float(rcfg["decision_time_utc_hour"]))
    fcfg, _ = load_config(CONFIGS["facility"])
    site = Site.from_facility(fcfg)
    outputs: dict[str, str] = {}
    spans: list[Span] = []
    t_all = time.time()
    for night in nights:
        t = night_t(night, float(rcfg["decision_time_utc_hour"]))
        t0 = time.time()
        snap = clock.snapshot(t, pool)
        snap_ms = (time.time() - t0) * 1000
        write(rdir / "snapshots" / f"{night}.json", snap.model_dump_json(), outputs, root)
        summary = [{
            "oid": c.oid, "ra": c.context.ra, "dec": c.context.dec, "gal_b": c.context.gal_b,
            "first_detection_mjd": c.first_detection_mjd, "last_detection_mjd": c.last_detection_mjd,
            "n_detections": c.n_detections, "n_nondetections": c.n_nondetections, "brightest_mag": c.brightest_mag,
            "latest_mag": c.latest_mag, "latest_band": c.latest_band,
            "fink_snn_snia_vs_nonia": next((r.snn_snia_vs_nonia for r in reversed(c.fink_rows) if r.snn_snia_vs_nonia is not None), None),
            "fink_cdsxmatch": next((r.cdsxmatch for r in reversed(c.fink_rows) if r.cdsxmatch), None),
            "fink_tns_alert_time": next((r.tns_alert_time for r in reversed(c.fink_rows) if r.tns_alert_time), None),
        } for c in snap.candidates]
        write(rdir / "pool" / f"{night}.json", json.dumps({"night": night, "t_mjd": t, "candidates": summary}, indent=1), outputs, root)
        t1 = time.time()
        header, frames = build_night(snap, site, run_id, "bench", chash, float(fcfg["min_altitude_deg"]),
                                     str(fcfg["site"].get("timezone", "UTC")))
        frames_ms = (time.time() - t1) * 1000
        theater = {"header": header.model_dump(), "frames": [f.model_dump() for f in frames]}
        write(rdir / "theater" / f"{night}.json", json.dumps(theater, separators=(",", ":")), outputs, root)
        spans.append(Span(span_id=f"{night}:snapshot", kind="replay", name="Clock.snapshot", latency_ms=round(snap_ms, 1),
                          attrs={"night": night, "t_mjd": t, "n_candidates": len(snap.candidates)}))
        spans.append(Span(span_id=f"{night}:theater", kind="replay", name="theater.build_night", latency_ms=round(frames_ms, 1),
                          attrs={"night": night, "n_frames": len(frames)}))
        print(f"{night}: pool={len(snap.candidates)} snapshot {snap_ms / 1000:.1f}s, theater {len(frames)} frames {frames_ms / 1000:.1f}s", flush=True)
    # Output hash over artifact contents only (wall-clock span latencies are excluded by construction).
    output_hash = sha256_hex(json.dumps(outputs, sort_keys=True))
    cfg = RunConfig(run_id=run_id, mode="bench", seed=args.seed, config_hash=chash, config_hashes=hashes, model_ids={},
                    code_version=code_version(), script="scripts/run_m1_spine.py")
    manifest = RunManifest(config=cfg, output_hash=output_hash, outputs=outputs, input_tokens=0, output_tokens=0, usd=0.0)
    (rdir / "manifest.json").write_text(manifest.model_dump_json(indent=1))
    with (root / f"{run_id}.jsonl").open("w") as fh:
        fh.write(json.dumps({"record": "run", **cfg.model_dump()}) + "\n")
        for s in spans:
            fh.write(json.dumps({"record": "span", **s.model_dump()}) + "\n")
        fh.write(json.dumps({"record": "end", "output_hash": output_hash, "usd": 0.0, "wall_s": round(time.time() - t_all, 1)}) + "\n")
    print(f"run_id={run_id}\noutput_hash={output_hash}\nartifacts={rdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
