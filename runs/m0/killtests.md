# M0 kill-tests (ARCHITECTURE §11)

Generated 2026-10-17T20:22:14+00:00 by `scripts/m0_killtests.py` (code unknown). No paid model calls were made.

| # | Assumption | Verdict | Fallback / note |
|---|---|---|---|
| 1 | TNS report/classification dates obtainable (individual bot) | **BLOCKED: CREDENTIAL REQUIRED** | Lasair/Fink TNS crossmatch tables (dates partial) — requires Fable decision (§14.7) if TNS stays unavailable **Needs Fable decision.** |
| 2 | Fink /objects POST returns per-alert d:* incl. d:tns, with upper limits | **PASS** |  |
| 5 | BTS CSV without filters includes unclassified saved candidates | **PASS** |  |
| 6 | Lasair token + Sherlock available; SIMBAD/NED rate limits tolerable with caching | **PASS** |  |
| 7 | Jev and Claude keys; Jev call ~200 ms with ~500-token state | **BLOCKED: CREDENTIAL REQUIRED** | M4 slips; architecture unaffected (§11) |
| 9 | CP-SAT solves 60 targets x 12 h in < 5 s | **PASS** |  |
| 10 | Corpus ingestion (AstroNotes/ATels/GCN) feasible with dates | **PARTIAL** | restrict to TNS + catalogs for M2 |
| 11 | Investigator decision impact may be small on easy candidates | **DEFERRED** | report null honestly; stratify |
| 12 | Jev first-option bias / literal reading | **DEFERRED** | randomize order, measure flips |

## Go / no-go

**Partial GO:** Blocked items do not block M1 (candidate spine); #1 (TNS) gates M2's prior-classification tool and Tier-A truth, #7 gates M2 extraction and all Jev roles.

## Evidence

### 1. TNS report/classification dates obtainable (individual bot)
*Test:* register; one query · *Verdict:* **BLOCKED: CREDENTIAL REQUIRED** · 0.6s
- **Credential:** `TNS_BOT_ID/TNS_BOT_NAME/TNS_API_KEY`
- **Setup:** Log in at https://www.wis-tns.org, open 'My account' -> 'Bots' -> 'Add bot', then add TNS_BOT_ID, TNS_BOT_NAME and TNS_API_KEY to .env.
- No TNS bot credentials in .env; no TNS call was attempted.
- Fallback inspected (not adopted): Lasair crossmatch_tns for ZTF25aaafbbk -> [('2025N', 'SN Ia', '2025-01-02T14:06:24.192000')]; columns=['decl', 'disc_date', 'disc_int_name', 'disc_mag', 'disc_mag_filter', 'ext_catalogs', 'host_name', 'hostz', 'htm16', 'id', 'lasairmodified_date', 'lastmodified_date', 'ra', 'reporters', 'sender', 'source_group', 'tns_name', 'tns_prefix', 'type', 'z']. It has disc_date and lastmodified_date but NO classification date, and `type` is the current TNS type.
- *Fallback:* Lasair/Fink TNS crossmatch tables (dates partial) — requires Fable decision (§14.7) if TNS stays unavailable — **requires Fable decision (§14.7)**

### 2. Fink /objects POST returns per-alert d:* incl. d:tns, with upper limits
*Test:* one POST · *Verdict:* **PASS** · 1.8s
- ZTF25aaafbbk: 33 rows, tags={'valid': 8, 'upperlim': 24, 'badquality': 1}; distinct alert jd per valid row: True
- missing required fields: none
- d:tns over time (jd-2460000, value): [(678.91, ''), (690.98, 'SN Ia'), (692.87, 'SN Ia'), (694.97, 'SN Ia'), (697.94, 'SN Ia'), (699.91, 'SN Ia')] — changes from '' to a class after the TNS report, consistent with alert-time crossmatch semantics
- quirk check ZTF25aaaalin: withupperlim=True -> 15 rows; withupperlim=False -> 10 rows. Mitigation: upper limits are taken from ALeRCE light curves; Fink is used for alert-time scores only.

### 5. BTS CSV without filters includes unclassified saved candidates
*Test:* one download · *Verdict:* **PASS** · 16.4s
- snapshot 2026-10-18: 20599 rows, 7682 unclassified (type '-'); columns ['ZTFID', 'IAUID', 'savedate', 'discdate', 'RA', 'Dec', 'peakt', 'peakfilt', 'peakmag', 'peakabs', 'duration', 'rise', 'fade', 'type', 'redshift', 'b', 'A_V']
- 2025 peaks: 2499 rows, 974 unclassified; top types [('-', 974), ('SN Ia', 949), ('SN II', 244), ('CV', 56), ('AGN', 39)]
- CSV has savedate/discdate but no classification date (as documented in §2.2).

### 6. Lasair token + Sherlock available; SIMBAD/NED rate limits tolerable with caching
*Test:* smoke tests · *Verdict:* **PASS** · 15.9s
- Lasair Sherlock (ZTF25aaafbbk): [('SN', 'UGC08239', 0.036, 22.964)]
- Lasair Sherlock position endpoint keys: ['classifications', 'crossmatches']
- SIMBAD: 10 cone searches (30"), errors=0, rows=1, median latency 0.25s (paced; cached thereafter)
- NED: 10 cone searches (30"), errors=0, rows=66, median latency 1.10s (paced; cached thereafter)

### 7. Jev and Claude keys; Jev call ~200 ms with ~500-token state
*Test:* one call each · *Verdict:* **BLOCKED: CREDENTIAL REQUIRED** · 0.0s
- **Credential:** `ANTHROPIC_API_KEY, TYPESAFE_API_KEY (or OPENROUTER_API_KEY)`
- **Setup:** ANTHROPIC_API_KEY: create at https://console.anthropic.com -> API keys. TYPESAFE_API_KEY: create at https://docs.typesafe.ai (quickstart) or use OPENROUTER_API_KEY (https://openrouter.ai/keys). Add to .env. Live calls are paid: the owner must also approve a spend budget.
- No model call attempted (keys absent; and no spend budget approved by the owner).
- *Fallback:* M4 slips; architecture unaffected (§11)

### 9. CP-SAT solves 60 targets x 12 h in < 5 s
*Test:* toy model · *Verdict:* **PASS** · 24.3s
- trial 0: status=OPTIMAL obj=733 bound=733 time=0.01s
- trial 1: status=OPTIMAL obj=702 bound=702 time=0.01s
- trial 2: status=OPTIMAL obj=727 bound=727 time=0.01s
- trial 3: status=OPTIMAL obj=736 bound=736 time=0.01s
- trial 4: status=OPTIMAL obj=743 bound=743 time=0.01s

### 10. Corpus ingestion (AstroNotes/ATels/GCN) feasible with dates
*Test:* crawl 1 month · *Verdict:* **PARTIAL** · 394.7s
- GCN: circulars 39543..39989: 447 dated in month, 0 fetch failures
- ATel: 65 telegrams dated in month (from #17059 to #17123); 0 unparseable; 'Referred to by' and 'Related' (later telegrams) stripped at parse time
- AstroNotes failed: RateLimited: astronote: HTTP 429: rate limited
- *Fallback:* restrict to TNS + catalogs for M2

### 11. Investigator decision impact may be small on easy candidates
*Test:* M3 design · *Verdict:* **DEFERRED** · 0.0s
- By architecture this is addressed in M3/M4 design (stratified easy/ambiguous/contaminant Tier-B; null results reported honestly). Not testable in M0.
- *Fallback:* report null honestly; stratify

### 12. Jev first-option bias / literal reading
*Test:* M4 · *Verdict:* **DEFERRED** · 0.0s
- By architecture measured in M4/M5 (option-order flip test). Also requires TYPESAFE_API_KEY and a spend budget (not configured).
- *Fallback:* randomize order, measure flips
