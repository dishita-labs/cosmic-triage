"""Dated text corpora for the Investigator (§2.2): GCN circulars, ATels, TNS AstroNotes.

Raw pages are cached verbatim; parsing strips content that post-dates the record itself
(ATel "Referred to by" back-links; AstroNote tooltips showing the object's *current* TNS type/redshift).
"""

from __future__ import annotations

import html as htmllib
import re
from datetime import UTC, datetime
from typing import Any

from astropy.time import Time

from cosmic_triage.ingest.cache import Cache
from cosmic_triage.ingest.http import HttpClient


def _strip_tags(s: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ").strip()


def _utc_to_mjd(dt: datetime) -> float:
    return float(Time(dt.replace(tzinfo=None), scale="utc").mjd)


class GcnClient:
    name = "gcn"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=0.5, offline=cache.offline)

    def circular(self, circular_id: int) -> dict[str, Any]:
        def fetch() -> dict[str, Any]:
            data: dict[str, Any] = self.http.request("GET", f"https://gcn.nasa.gov/circulars/{circular_id}.json").json()
            return data

        raw: dict[str, Any] = self.cache.get_or_fetch(self.name, "circular", {"id": circular_id}, fetch)
        created = datetime.fromtimestamp(raw["createdOn"] / 1000.0, tz=UTC)
        return {
            "id": f"GCN{raw['circularId']}", "source_date": _utc_to_mjd(created), "title": raw.get("subject", ""),
            "event": raw.get("eventId"), "body": raw.get("body", ""),
        }


ATEL_DATE = re.compile(r"on <STRONG>(\d{1,2} \w{3} \d{4}); (\d{1,2}:\d{2}) UT</STRONG>")


def parse_atel(page: str, number: int) -> dict[str, Any] | None:
    m = ATEL_DATE.search(page)
    if not m:
        return None
    dt = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d %b %Y %H:%M")
    title_m = re.search(r'<h1 class="title">(.*?)</h1>', page, re.S)
    subj_m = re.search(r'<p class="subjects">(.*?)</P>', page, re.S | re.I)
    # The body sits between the references block and the next <div id=...> (the "Related" side panel).
    # Both "Referred to by" and "Related" list *later* telegrams -> leakage if read as of this date; dropped.
    tail = page.split('</div id="references">', 1)[1] if '</div id="references">' in page else page
    tail = tail.split("<div id=", 1)[0]
    tail = re.sub(r"<script.*?</script>", " ", tail, flags=re.S | re.I)
    text = re.sub(r"\s+", " ", _strip_tags(tail)).removeprefix("Tweet").strip()
    return {
        "id": f"ATel{number}", "source_date": _utc_to_mjd(dt.replace(tzinfo=UTC)),
        "title": _strip_tags(title_m.group(1)) if title_m else "",
        "subjects": _strip_tags(subj_m.group(1)).removeprefix("Subjects:").strip() if subj_m else "",
        "body": text[:20000],
    }


class AtelClient:
    name = "atel"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=1.0, offline=cache.offline)

    def raw(self, number: int) -> str:
        def fetch() -> str:
            return self.http.request("GET", "https://www.astronomerstelegram.org/", params={"read": number}).text

        page: str = self.cache.get_or_fetch(self.name, "telegram", {"read": number}, fetch)
        return page

    def telegram(self, number: int) -> dict[str, Any] | None:
        return parse_atel(self.raw(number), number)


NOTE_BLOCK = re.compile(r'<div id="note-(\d{4}-\d+)" class="note .*?(?=<div id="note-\d{4}-\d+" class="note |\Z)', re.S)


def parse_astronote_listing(page: str) -> list[dict[str, Any]]:
    out = []
    for m in NOTE_BLOCK.finditer(page):
        block = m.group(0)
        rel = re.search(r'class="note-lastmodified">([\d\- :]+)</span>', block)
        title = re.search(r'class="note-title">(.*?)</div>', block, re.S)
        ntype = re.search(r'class="note-type-link">(.*?)</a>', block, re.S)
        # Object names only; tooltips carry the object's *current* TNS type/redshift (post-dated) -> dropped.
        objs = re.findall(r'class="object-tooltip-link">(.*?)</a>', block, re.S)
        abstract = re.search(r'class="note-abstract">(.*?)</div>', block, re.S)
        if not rel:
            continue
        stamp = rel.group(1).strip()
        fmt = "%Y-%m-%d %H:%M:%S" if " " in stamp else "%Y-%m-%d"
        dt = datetime.strptime(stamp, fmt).replace(tzinfo=UTC)
        out.append({
            "id": f"AstroNote{m.group(1)}", "source_date": _utc_to_mjd(dt),
            "source_date_kind": "last_modified",
            "title": _strip_tags(title.group(1)) if title else "",
            "type": _strip_tags(ntype.group(1)) if ntype else "",
            "objects": [_strip_tags(o) for o in objs],
            "abstract": _strip_tags(abstract.group(1)) if abstract else "",
        })
    return out


class AstroNoteClient:
    name = "astronote"

    def __init__(self, cache: Cache, http: HttpClient | None = None) -> None:
        self.cache = cache
        self.http = http or HttpClient(self.name, min_interval_s=2.0, offline=cache.offline)

    def listing_raw(self, page: int) -> str:
        def fetch() -> str:
            return self.http.request("GET", "https://www.wis-tns.org/astronotes", params={"page": page}).text

        text: str = self.cache.get_or_fetch(self.name, "listing", {"page": page}, fetch)
        return text

    def listing(self, page: int) -> list[dict[str, Any]]:
        return parse_astronote_listing(self.listing_raw(page))
