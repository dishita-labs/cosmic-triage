"""Write synthetic GCN / ATel / AstroNote fixtures for the offline corpus-parser tests.

The text corpora are third-party publications, so the fixtures do not redistribute them: each payload reproduces
only the page *structure* the parsers in ``cosmic_triage.ingest.corpora`` rely on (date stamp, title, references
block, related-telegrams panel, AstroNote tooltips), with invented wording. They keep the leakage cases the tests
check: later-telegram back-links in an ATel and current-type/redshift tooltips in an AstroNote listing.
Offline; no network. Usage: uv run python scripts/make_corpus_fixtures.py
"""

from __future__ import annotations

import sys

from cosmic_triage.ingest import Cache
from cosmic_triage.settings import PROJECT_ROOT

SYNTHETIC = "SYNTHETIC TEST FIXTURE: invented text, not a real publication."

GCN = {
    "circularId": 39000,
    "createdOn": 1737386652891,  # 2025-01-20 15:24:12 UTC (the date the parser test checks)
    "eventId": "GRB 000000A",
    "format": "text/plain",
    "subject": "GRB 000000A: synthetic test circular",
    "submittedHow": "web",
    "submitter": "Test Author at Example Observatory",
    "body": f"{SYNTHETIC}\nTest Author (Example Observatory) reports on behalf of the Example team:\n"
            "A synthetic afterglow candidate was observed at a placeholder position. No real data.",
}


def _atel_ref(n: int) -> str:
    return f'<A HREF="https://www.astronomerstelegram.org/?read={n}">{n}</a>'


ATEL = f"""<html><head><title>ATel #17100: synthetic test telegram</title>
<script type="text/javascript">var page = "synthetic";</script></head><body>
<div id="header"><p>Synthetic header</p></div>
<div id="telegram"><h1 class="title">Synthetic transient detected by the Einstein Probe test fixture</h1>
<P><EM><STRONG><A HREF="mailto:none">Test Author (Example Observatory)</A> on behalf of the Einstein Probe team:</A></STRONG><BR>
 on <STRONG>22 Mar 2025; 07:39 UT</STRONG><BR><EM>Credential: Test Author (Example Observatory)</EM></EM></P>
<div id="subjects"><p class="subjects">Subjects: Optical, X-ray, Transient</P></div id="subjects">
<div id="references"><p>Referred to by ATel #:  {_atel_ref(17101)},   {_atel_ref(17195)}</p></div id="references">
<script type="text/javascript">var tweet = 1;</script>Tweet
<P>{SYNTHETIC} The Einstein Probe test team reports a synthetic X-ray transient at a placeholder position.
Follow-up is encouraged. This paragraph is the telegram body the parser keeps.</P>
<div id="related"><p>Related: {_atel_ref(17101)} Synthetic later telegram; {_atel_ref(17195)} Another later telegram</p></div>
</div></body></html>
"""


def _note(note_id: str, released: str, title: str, objname: str, cur_type: str, cur_z: str) -> str:
    return (
        f'<div id="note-{note_id}" class="note note-{note_id} clearfix note-public" note-id="{note_id}" row-index="0">'
        '<div class="note-data-wrapper"><div class="note-top">'
        f'<div class="note-top-param note-id"><a href="https://www.wis-tns.org/astronotes/astronote/{note_id}" '
        f'class="note-link">AstroNote {note_id}</a></div>'
        '<div class="note-top-param type">Type: <a href="#" class="note-type-link">Classification</a></div>'
        f'<div class="note-top-param latmodified">Released: <span class="note-lastmodified">{released}</span></div></div>'
        f'<div class="row-data"><div class="note-title">{title}</div>'
        '<div class="note-coauthors">Test Author (Example Observatory)</div>'
        '<div class="note-objects"><span class="field-title">Related Objects: </span><div class="object-wrapper">'
        f'<a href="javascript:void(0)" ra="00:00:00.000" dec="+00:00:00.00" class="object-tooltip-link">{objname}</a>'
        '<div class="object-tooltip description"><span class="tooltip-arrow-outer"></span>'
        '<div class="tooltip-line"><span class="tootip-line-title">RA, DEC:</span>00:00:00.000 +00:00:00.00</div>'
        f'<div class="tooltip-line"><span class="tootip-line-title">Redshift:</span>{cur_z}</div>'
        f'<div class="tooltip-line"><span class="tootip-line-title">Type:</span>{cur_type}</div>'
        '<span class="tooltip-arrow-inner"></span></div></div></div>'
        f'<div class="note-abstract">{SYNTHETIC} Synthetic abstract for {objname}.</div></div></div></div>\n'
    )


ASTRONOTE = (
    "<html><body><div class=\"notes-list\">\n"
    + _note("2026-291", "2026-10-14 15:53:52", "Synthetic classification note A", "2026aaa", "SN Ia", "0.05")
    + _note("2026-290", "2026-10-13 09:12:05", "Synthetic classification note B", "2026aab", "SN II", "0.02")
    + _note("2026-289", "2026-10-12", "Synthetic follow-up note C", "2026aac", "", "")
    + "</div></body></html>\n"
)


def main() -> int:
    fx = Cache(root=PROJECT_ROOT / "tests" / "fixtures" / "cache", offline=False)
    fx.put("gcn", "circular", {"id": 39000}, GCN)
    fx.put("atel", "telegram", {"read": 17100}, ATEL)
    fx.put("astronote", "listing", {"page": 0}, ASTRONOTE)
    print("wrote synthetic gcn.circular, atel.telegram, astronote.listing fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
