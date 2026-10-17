"""Every external client parses its recorded fixture offline (M0: recorded fixtures for every API touched)."""

from __future__ import annotations

import pytest

from cosmic_triage.ingest import AlerceClient, CredentialMissing, FinkClient, LasairClient, OfflineCacheMiss, TNSClient
from cosmic_triage.ingest.catalogs import NedClient, SimbadClient
from cosmic_triage.ingest.corpora import AstroNoteClient, AtelClient, GcnClient

PROBE = "ZTF25aaafbbk"


def test_alerce_lightcurve(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    lc = AlerceClient(fixture_cache).lightcurve(PROBE)
    assert lc["detections"] and "non_detections" in lc
    assert {"mjd", "magpsf", "fid", "drb", "isdiffpos"} <= set(lc["detections"][0])


def test_alerce_probabilities_and_stamp(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    a = AlerceClient(fixture_cache)
    probs = a.probabilities(PROBE)
    assert any(p["classifier_name"] == "stamp_classifier" for p in probs)
    cand = str(next(d["candid"] for d in a.lightcurve(PROBE)["detections"] if d.get("has_stamp")))
    assert a.stamp(PROBE, cand, "science")[:4] == b"\x89PNG"


def test_alerce_objects_fixture(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    objs = AlerceClient(fixture_cache).objects((60760.2, 60760.25), ndet=[2, 100000])
    assert objs and all(60760.2 <= o["firstmjd"] < 60760.25 and o["ndet"] >= 2 for o in objs)


def test_alerce_pagination_continues_on_full_pages(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import httpx

    from cosmic_triage.ingest import Cache, HttpClient

    pages = {1: [{"oid": "a"}, {"oid": "b"}], 2: [{"oid": "c"}, {"oid": "d"}], 3: [{"oid": "e"}]}

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params["page"])
        return httpx.Response(200, json={"items": pages.get(page, []), "has_next": False, "total": None})

    h = HttpClient("alerce", offline=False)
    h._client = httpx.Client(transport=httpx.MockTransport(handler))
    a = AlerceClient(Cache(root=tmp_path, offline=False), http=h)
    assert [o["oid"] for o in a.objects((1.0, 2.0), page_size=2)] == ["a", "b", "c", "d", "e"]


def test_fink_rows(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    rows = FinkClient(fixture_cache).object_rows(PROBE)
    assert {r["d:tag"] for r in rows} >= {"valid", "upperlim"}
    assert all("d:tns" in r for r in rows if r["d:tag"] == "valid")


def test_lasair_queries(fixture_cache, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    las = LasairClient(fixture_cache)
    sher = las.sherlock_object(PROBE)
    assert sher and sher[0]["classification"] == "SN"
    tns = las.tns_crossmatch(PROBE)
    assert tns and tns[0]["tns_name"] == "2025N"


def test_lasair_rejects_injection() -> None:
    from cosmic_triage.ingest.lasair import _safe_oid

    with pytest.raises(ValueError):
        _safe_oid("ZTF25' OR 1=1 --")


def test_tns_requires_credentials(fixture_cache, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for n in ("TNS_BOT_ID", "TNS_BOT_NAME", "TNS_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr("cosmic_triage.settings._dotenv", lambda: {})
    with pytest.raises(CredentialMissing) as ei:
        TNSClient(fixture_cache).search(197.3, 46.2)
    assert "BLOCKED: CREDENTIAL REQUIRED" in str(ei.value)


def test_lasair_requires_token_when_not_cached(fixture_cache, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LASAIR_TOKEN", raising=False)
    monkeypatch.setattr("cosmic_triage.settings._dotenv", lambda: {})
    with pytest.raises((CredentialMissing, OfflineCacheMiss)):
        LasairClient(fixture_cache).object("ZTF99zzzzzzz")


def test_simbad_ned(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    assert SimbadClient(fixture_cache).cone(186.27, 12.887, 60)
    assert NedClient(fixture_cache).cone(186.27, 12.887, 60)


def test_gcn(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    c = GcnClient(fixture_cache).circular(39000)
    assert c["id"] == "GCN39000" and 60690 < c["source_date"] < 60700


def test_atel_strips_later_references(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    a = AtelClient(fixture_cache).telegram(17100)
    assert a is not None and abs(a["source_date"] - 60756.31875) < 1e-6
    assert "Referred to by" not in a["body"]
    assert "17101" not in a["body"] and "17195" not in a["body"]  # later telegrams never leak into the body
    assert "Einstein Probe" in a["body"]


def test_astronote_strips_current_type(fixture_cache) -> None:  # type: ignore[no-untyped-def]
    notes = AstroNoteClient(fixture_cache).listing(0)
    assert notes and all("source_date" in n for n in notes)
    assert all("Redshift" not in " ".join(n["objects"]) and "Type:" not in " ".join(n["objects"]) for n in notes)
