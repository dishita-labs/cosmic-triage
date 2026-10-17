"""ALeRCE public read-only PostgreSQL access (forward-pool superset queries over full-history aggregates).

ALeRCE publishes read-only credentials for public use at ``CREDENTIALS_URL``; they are fetched at query time,
never stored. Query results go through the shared Cache, so offline rebuilds never touch the database.
"""

from __future__ import annotations

import json
from typing import Any

from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.errors import ExternalAPIError, NetworkDisabled
from cosmic_triage.ingest.http import HttpClient

CREDENTIALS_URL = "https://raw.githubusercontent.com/alercebroker/usecases/master/alercereaduser_v4.json"

SUPERSET_SQL = """
select o.oid, o.firstmjd, o.meanra, o.meandec,
       bool_or(ps.sgscore1 is null or ps.distpsnr1 is null
               or not (ps.sgscore1 >= %(star_sg)s and ps.distpsnr1 < %(star_dist)s)) as any_nonstellar_ps1,
       min(ps.sgscore1) as sgscore1_min, min(ps.distpsnr1) as distpsnr1_min, min(ps.srmag1) as srmag1_min
from object o
left join ps1_ztf ps on ps.oid = o.oid
where o.firstmjd >= %(lo)s and o.firstmjd < %(hi)s and o.ndet >= %(min_ndet)s
  and exists (select 1 from magstat m where m.oid = o.oid and m.magmin <= %(max_mag)s)
group by o.oid, o.firstmjd, o.meanra, o.meandec
"""


class AlerceDBClient:
    name = "alerce_db"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, offline=cache.offline)
        self._conn: Any = None

    def _connect(self) -> Any:
        if self.cache.offline:
            raise NetworkDisabled("alerce_db: offline")
        if self._conn is None:
            import psycopg

            p = json.loads(self.http.request("GET", CREDENTIALS_URL).text)["params"]
            try:
                self._conn = psycopg.connect(
                    host=p["host"], dbname=p["dbname"], user=p["user"], password=p["password"], connect_timeout=30
                )
            except psycopg.Error as exc:
                raise ExternalAPIError(self.name, None, f"connect failed: {type(exc).__name__}") from None
        return self._conn

    def superset_day(self, day_mjd: int, max_mag: float, min_ndet: int, star_sg: float, star_dist: float) -> list[dict[str, Any]]:
        """Objects first alerted in [day, day+1) with final ndet >= min_ndet and all-time brightest <= max_mag.

        Both conditions are monotone over an object's history (necessary for any t after the first alert).
        Position and PS1-counterpart fields are static context."""
        params = {"lo": float(day_mjd), "hi": float(day_mjd + 1), "max_mag": max_mag, "min_ndet": min_ndet,
                  "star_sg": star_sg, "star_dist": star_dist}

        def fetch() -> list[dict[str, Any]]:
            cur = self._connect().execute(SUPERSET_SQL, params)
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

        result: list[dict[str, Any]] = self.cache.get_or_fetch(self.name, "superset_day_v1", params, fetch)
        return result
