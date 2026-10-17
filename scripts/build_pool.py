"""Warm the cache for the M1 nights and write per-night forward pools to runs/m1/.

Online use only (fetches from ALeRCE/Lasair/Fink). Re-running with COSMIC_OFFLINE=1 rebuilds from cache.
Usage: uv run python scripts/build_pool.py [--nights 2025-04-01,...]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from cosmic_triage.ingest import AlerceClient, Cache, FinkClient
from cosmic_triage.ingest.alerce_db import AlerceDBClient
from cosmic_triage.replay.pool import ForwardPool, night_t
from cosmic_triage.settings import PROJECT_ROOT, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_pool")


def main() -> int:
    replay_cfg, _ = load_config("configs/replay/replay.yaml")
    ap = argparse.ArgumentParser()
    ap.add_argument("--nights", default=",".join(replay_cfg["m1_nights"]))
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    nights = args.nights.split(",")
    cache = Cache()
    pool = ForwardPool(AlerceClient(cache), FinkClient(cache), AlerceDBClient(cache), workers=args.workers)
    out_dir = PROJECT_ROOT / "runs" / "m1" / "pools"
    out_dir.mkdir(parents=True, exist_ok=True)
    for night in nights:
        t = night_t(night, float(replay_cfg["decision_time_utc_hour"]))
        t0 = time.time()
        sup = pool.superset(t)
        log.info("night %s t=%.4f superset=%d (%.1fs)", night, t, len(sup), time.time() - t0)
        hyd = pool.hydrate_many(sup)
        errs = {o: repr(e) for o, e in hyd.items() if isinstance(e, Exception)}
        log.info("night %s hydrated=%d errors=%d (%.1fs)", night, len(hyd) - len(errs), len(errs), time.time() - t0)
        if errs:
            (out_dir / f"{night}.errors.json").write_text(json.dumps(errs, indent=1))
            log.error("hydration errors for %s; see %s.errors.json", night, night)
            continue
        res = pool.evaluate_all(t)
        members = sorted(o for o, r in res.items() if r.passed)
        (out_dir / f"{night}.json").write_text(json.dumps({
            "night": night, "t_mjd": t, "prefilter_hash": pool.cfg.config_hash,
            "n_superset": len(res), "members": members,
            "reasons": {o: list(r.reasons) for o, r in sorted(res.items()) if not r.passed},
        }, indent=1))
        log.info("night %s pool=%d (%.1fs) cache hits=%d misses=%d", night, len(members), time.time() - t0,
                 cache.hits, cache.misses)
    return 0


if __name__ == "__main__":
    sys.exit(main())
