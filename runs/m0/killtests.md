# M0 kill-tests (ARCHITECTURE §11)

Generated 2026-10-18T10:36:33+00:00 by `scripts/m0_killtests.py` (code ebf9062-dirty). No paid model calls were made.

| # | Assumption | Verdict | Fallback / note |
|---|---|---|---|
| 1 | TNS report/classification dates obtainable (individual bot) | **BLOCKED: CREDENTIAL REQUIRED** | Lasair/Fink TNS crossmatch tables (dates partial) — requires Fable decision (§14.7) if TNS stays unavailable **Needs Fable decision.** |
| 2 | Fink /objects POST returns per-alert d:* incl. d:tns, with upper limits | **PASS** |  |
| 3 | Forward-pool volume per night manageable (<= ~500 after pre-filter) | **PASS** |  |
| 4 | Budget binds: median(bright SN-like candidates)/slots >= 2 | **PASS** |  |
| 5 | BTS CSV without filters includes unclassified saved candidates | **PASS** |  |
| 6 | Lasair token + Sherlock available; SIMBAD/NED rate limits tolerable with caching | **PASS** |  |
| 7 | Jev and Claude keys; Jev call ~200 ms with ~500-token state | **BLOCKED: SPEND APPROVAL REQUIRED** | M4 slips; architecture unaffected (§11) |
| 8 | btsbot installs and runs on ALeRCE stamps | **PASS** |  |
| 9 | CP-SAT solves 60 targets x 12 h in < 5 s | **PASS** |  |
| 10 | Corpus ingestion (AstroNotes/ATels/GCN) feasible with dates | **PASS** |  |
| 11 | Investigator decision impact may be small on easy candidates | **DEFERRED** | report null honestly; stratify |
| 12 | Jev first-option bias / literal reading | **DEFERRED** | randomize order, measure flips |

## Go / no-go

**Partial GO:** Blocked items do not block M1 (candidate spine); #1 (TNS) gates M2's prior-classification tool and Tier-A truth, #7 gates M2 extraction and all Jev roles.

## Evidence

### 1. TNS report/classification dates obtainable (individual bot)
*Test:* register; one query · *Verdict:* **BLOCKED: CREDENTIAL REQUIRED** · 0.0s
- **Credential:** `TNS_BOT_ID/TNS_BOT_NAME/TNS_API_KEY`
- **Setup:** Log in at https://www.wis-tns.org, open 'My account' -> 'Bots' -> 'Add bot', then add TNS_BOT_ID, TNS_BOT_NAME and TNS_API_KEY to .env.
- No TNS bot credentials in .env; no TNS call was attempted.
- Fallback inspected (not adopted): Lasair crossmatch_tns for ZTF25aaafbbk -> [('2025N', 'SN Ia', '2025-01-02T14:06:24.192000')]; columns=['decl', 'disc_date', 'disc_int_name', 'disc_mag', 'disc_mag_filter', 'ext_catalogs', 'host_name', 'hostz', 'htm16', 'id', 'lasairmodified_date', 'lastmodified_date', 'ra', 'reporters', 'sender', 'source_group', 'tns_name', 'tns_prefix', 'type', 'z']. It has disc_date and lastmodified_date but NO classification date, and `type` is the current TNS type.
- *Fallback:* Lasair/Fink TNS crossmatch tables (dates partial) — requires Fable decision (§14.7) if TNS stays unavailable — **requires Fable decision (§14.7)**

### 2. Fink /objects POST returns per-alert d:* incl. d:tns, with upper limits
*Test:* one POST · *Verdict:* **PASS** · 0.0s
- ZTF25aaafbbk: 33 rows, tags={'valid': 8, 'upperlim': 24, 'badquality': 1}; distinct alert jd per valid row: True
- missing required fields: none
- d:tns over time (jd-2460000, value): [(678.91, ''), (690.98, 'SN Ia'), (692.87, 'SN Ia'), (694.97, 'SN Ia'), (697.94, 'SN Ia'), (699.91, 'SN Ia')] — changes from '' to a class after the TNS report, consistent with alert-time crossmatch semantics
- quirk check ZTF25aaaalin: withupperlim=True -> 15 rows; withupperlim=False -> 10 rows (during M0 probing the withupperlim=True call once returned [] for this object — transient). Mitigation: upper limits are taken from ALeRCE light curves; Fink is used for alert-time scores only.

### 3. Forward-pool volume per night manageable (<= ~500 after pre-filter)
*Test:* 5 nights of /objects?firstmjd · *Verdict:* **PASS** · 1.1s
- pool size after time-honest pre-filter per night: {'2025-04-19': 95, '2025-04-20': 104, '2025-04-21': 103, '2025-04-22': 102, '2025-04-23': 102} (median 102)
- per night: ALeRCE objects first alerted that UTC day with final ndet>=2 (REST /objects?firstmjd) / that day's superset after necessary cuts (all-time brightest <= 19, |b|, PS1 star) / 15-day window superset hydrated: 2025-04-19: 55/12/2785, 2025-04-20: 2758/402/2889, 2025-04-21: 11230/238/3032, 2025-04-22: 3543/462/3208, 2025-04-23: 1010/153/3045

### 4. Budget binds: median(bright SN-like candidates)/slots >= 2
*Test:* count over candidate window · *Verdict:* **PASS** · 1.0s
- bright (brightest qualifying mag <= 18.5 at t) & SN-like (latest alert-time Fink cdsxmatch not stellar/AGN) pool members per night: {'2025-04-19': 59, '2025-04-20': 62, '2025-04-21': 52, '2025-04-22': 51, '2025-04-23': 47}; median 52
- largest budget with median/slots >= 2: 26 spectra/night (architecture floor if the sky is thin: 3-4 spectra/night)

### 5. BTS CSV without filters includes unclassified saved candidates
*Test:* one download · *Verdict:* **PASS** · 0.4s
- snapshot 2026-10-18: 20599 rows, 7682 unclassified (type '-'); columns ['ZTFID', 'IAUID', 'savedate', 'discdate', 'RA', 'Dec', 'peakt', 'peakfilt', 'peakmag', 'peakabs', 'duration', 'rise', 'fade', 'type', 'redshift', 'b', 'A_V']
- 2025 peaks: 2499 rows, 974 unclassified; top types [('-', 974), ('SN Ia', 949), ('SN II', 244), ('CV', 56), ('AGN', 39)]
- CSV has savedate/discdate but no classification date (as documented in §2.2).

### 6. Lasair token + Sherlock available; SIMBAD/NED rate limits tolerable with caching
*Test:* smoke tests · *Verdict:* **PASS** · 0.0s
- Lasair Sherlock (ZTF25aaafbbk): [('SN', 'UGC08239', 0.036, 22.964)]
- Lasair Sherlock position endpoint keys: ['classifications', 'crossmatches']
- SIMBAD: 10 cone searches (30"), errors=0, rows=1, median latency 0.00s (paced; cached thereafter)
- NED: 10 cone searches (30"), errors=0, rows=66, median latency 0.00s (paced; cached thereafter)

### 7. Jev and Claude keys; Jev call ~200 ms with ~500-token state
*Test:* one call each · *Verdict:* **BLOCKED: SPEND APPROVAL REQUIRED** · 0.0s
- Keys present, but the owner has not approved a model spend budget; no paid call made.
- *Fallback:* M4 slips; architecture unaffected (§11)

### 8. btsbot installs and runs on ALeRCE stamps
*Test:* inference on 10 alerts · *Verdict:* **PASS** · 0.0s
- btsbot 2.0.6 (torch 2.14.1) installed in an isolated venv; model nabeelr/BTSbot-convnext-pico-galaxyzoo (image-only)
- 10 first-alert ALeRCE FITS triplets scored on CPU; load 12.1s, inference 0.22s
- scores (sigmoid; higher = BTS-worthy SN-like): ZTF25aaaalin (SN Ia): 0.462; ZTF25aaaauxw (SN Ia): 0.762; ZTF25aaaawig (SN Ia): 0.157; ZTF25aaabezb (SN Ia): 0.537; ZTF25aaabnxh (SN Ia): 0.119; ZTF25aacawsr (AGN): 0.220; ZTF25aaqvwgk (CV): 0.997; ZTF25aaynaqk (CV): 0.261; ZTF25abmwwga (CV): 0.872; ZTF25absjvvl (CV): 0.991
- Image-only model used (the multimodal variant also needs 25 alert-packet features; M7 work).

### 9. CP-SAT solves 60 targets x 12 h in < 5 s
*Test:* toy model · *Verdict:* **PASS** · 0.4s
- trial 0: status=OPTIMAL obj=733 bound=733 time=0.03s
- trial 1: status=OPTIMAL obj=702 bound=702 time=0.01s
- trial 2: status=OPTIMAL obj=727 bound=727 time=0.01s
- trial 3: status=OPTIMAL obj=736 bound=736 time=0.01s
- trial 4: status=OPTIMAL obj=743 bound=743 time=0.01s

### 10. Corpus ingestion (AstroNotes/ATels/GCN) feasible with dates
*Test:* crawl 1 month · *Verdict:* **PASS** · 0.4s
- GCN: circulars 39543..39989: 447 dated in month, 0 fetch failures
- ATel: 65 telegrams dated in month (from #17059 to #17123); 0 unparseable; 'Referred to by' and 'Related' (later telegrams) stripped at parse time
- AstroNotes: 29 notes with release/last-modified date in month (scanned 80 listing pages); date is 'last modified' (may post-date first release) — as-of filter must treat it as an upper bound; object tooltips with current TNS type/redshift stripped

### 11. Investigator decision impact may be small on easy candidates
*Test:* M3 design · *Verdict:* **DEFERRED** · 0.0s
- By architecture this is addressed in M3/M4 design (stratified easy/ambiguous/contaminant Tier-B; null results reported honestly). Not testable in M0.
- *Fallback:* report null honestly; stratify

### 12. Jev first-option bias / literal reading
*Test:* M4 · *Verdict:* **DEFERRED** · 0.0s
- By architecture measured in M4/M5 (option-order flip test). Also requires TYPESAFE_API_KEY and a spend budget (not configured).
- *Fallback:* randomize order, measure flips
