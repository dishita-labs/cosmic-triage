"""TNS client (bot API) for report/classification dates (§2.2, kill-test #1).

Requires a TNS *bot* (``TNS_BOT_ID``, ``TNS_BOT_NAME``, ``TNS_API_KEY``). Without them every call raises
``CredentialMissing``; the fallback (Lasair/Fink TNS tables) requires a Fable decision (§14.7).
"""

from __future__ import annotations

import json
from typing import Any

from cosmic_triage import settings
from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.errors import CredentialMissing
from cosmic_triage.ingest.http import HttpClient

BASE = "https://www.wis-tns.org/api/get"
HOW = (
    "Log in at https://www.wis-tns.org, open 'My account' -> 'Bots' -> 'Add bot', then add "
    "TNS_BOT_ID, TNS_BOT_NAME and TNS_API_KEY to .env."
)


class TNSClient:
    name = "tns"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=2.0, offline=cache.offline)

    @staticmethod
    def credentials_present() -> bool:
        return all(settings.get_secret(n) for n in ("TNS_BOT_ID", "TNS_BOT_NAME", "TNS_API_KEY"))

    def _auth(self) -> tuple[dict[str, str], str]:
        bot_id = settings.get_secret("TNS_BOT_ID")
        bot_name = settings.get_secret("TNS_BOT_NAME")
        key = settings.get_secret("TNS_API_KEY")
        if not (bot_id and bot_name and key):
            missing = [n for n, v in (("TNS_BOT_ID", bot_id), ("TNS_BOT_NAME", bot_name), ("TNS_API_KEY", key)) if not v]
            raise CredentialMissing("/".join(missing), HOW)
        marker = "tns_marker" + json.dumps({"tns_id": int(bot_id), "type": "bot", "name": bot_name})
        return {"User-Agent": marker}, key

    def _call(self, endpoint: str, obj: dict[str, Any]) -> Any:
        headers, key = self._auth()
        resp = self.http.request(
            "POST", f"{BASE}/{endpoint}", data={"api_key": key, "data": json.dumps(obj)}, headers=headers
        )
        return resp.json().get("data")

    def search(self, ra: float, dec: float, radius_arcsec: float = 3.0) -> list[dict[str, Any]]:
        obj = {"ra": f"{ra:.6f}", "dec": f"{dec:.6f}", "radius": radius_arcsec, "units": "arcsec"}
        self._auth()  # fail fast, before any cache lookup, so blocked status is explicit
        result: list[dict[str, Any]] = self.cache.get_or_fetch(self.name, "search", obj, lambda: self._call("search", obj))
        return result

    def get_object(self, name: str) -> dict[str, Any]:
        obj = {"objname": name, "classification": "1", "spectra": "0", "photometry": "0"}
        self._auth()
        result: dict[str, Any] = self.cache.get_or_fetch(self.name, "object", obj, lambda: self._call("object", obj))
        return result
