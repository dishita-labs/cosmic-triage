# Labels audit — contaminant spot-check (M1.1)

*Prepared by Opus for the owner. Status: **AWAITING OWNER REVIEW** — no human judgements recorded yet. Contaminant labels are provisional until this audit is complete (ARCHITECTURE §6.4, Review-03 (c)).*

## What is being audited

Rule under test (§6.4): a forward-pool member that BTS **never saved**, that passed the time-honest pre-filter, and whose brightest *qualifying* detection (drb ≥ 0.5, positive subtraction) over its full history is ≤ 18.5 mag is labelled **contaminant** (justified by the BTS II TNS audit, ~0.6% missed SNe).

Population: **50 unique contaminant objects** in the M1 nights 2025-04-19, 2025-04-20, 2025-04-21, 2025-04-22, 2025-04-23 under pre-filter `9669bcad8c932e03` (v1.1, known-at-t rule + per-alert history). Sample: **30 objects** drawn uniformly at random with `random.Random(20261018)` (`scripts/labels_audit.py`).

**Decision rule (pre-registered, §6.4 (c)):** if more than 5% of audited objects look like genuine SNe (i.e. ≥ 2 of 30), the rule tightens to require non-SN contextual evidence and otherwise label the object **unknown**.

## How to review (≈ 1–2 min per object)

1. Open the ALeRCE or Lasair link: look at the light curve (rise/fall over weeks = SN-like; erratic or years-long variability = AGN/variable star; a pair of detections on one night and never again = moving object or bogus) and the cutout triplet.
2. Open the TNS cone link: is there a TNS object at this position, and was it classified as an SN?
3. Open Legacy Survey: is the source on a galaxy nucleus, offset in a galaxy, or a point source (star)?
4. Fill in the verdict below (or in `runs/m1/m1.1/labels_audit_form.csv`). Please judge **before** reading the context section at the end, to avoid anchoring on the machine classifications.

## Form

| # | OID | Links | Verdict (SN / not SN / unsure) | If not SN: what (asteroid/moving, AGN, CV, star, bogus, nuclear var., other) | Notes |
|---|---|---|---|---|---|
| 1 | `ZTF25aalvose` | [ALeRCE](https://alerce.online/object/ZTF25aalvose) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aalvose/) · [Fink](https://fink-portal.org/ZTF25aalvose) · [TNS cone 5″](https://www.wis-tns.org/search?ra=244.528874&decl=-11.312315&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=244.528874&dec=-11.312315&layer=ls-dr10&zoom=16&mark=244.528874,-11.312315) | | | |
| 2 | `ZTF25aalvpuf` | [ALeRCE](https://alerce.online/object/ZTF25aalvpuf) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aalvpuf/) · [Fink](https://fink-portal.org/ZTF25aalvpuf) · [TNS cone 5″](https://www.wis-tns.org/search?ra=282.992581&decl=-17.279468&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=282.992581&dec=-17.279468&layer=ls-dr10&zoom=16&mark=282.992581,-17.279468) | | | |
| 3 | `ZTF25aalzdap` | [ALeRCE](https://alerce.online/object/ZTF25aalzdap) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aalzdap/) · [Fink](https://fink-portal.org/ZTF25aalzdap) · [TNS cone 5″](https://www.wis-tns.org/search?ra=272.385986&decl=70.951677&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=272.385986&dec=70.951677&layer=ls-dr10&zoom=16&mark=272.385986,70.951677) | | | |
| 4 | `ZTF25aamaxbv` | [ALeRCE](https://alerce.online/object/ZTF25aamaxbv) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamaxbv/) · [Fink](https://fink-portal.org/ZTF25aamaxbv) · [TNS cone 5″](https://www.wis-tns.org/search?ra=295.459707&decl=38.297619&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=295.459707&dec=38.297619&layer=ls-dr10&zoom=16&mark=295.459707,38.297619) | | | |
| 5 | `ZTF25aamhede` | [ALeRCE](https://alerce.online/object/ZTF25aamhede) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamhede/) · [Fink](https://fink-portal.org/ZTF25aamhede) · [TNS cone 5″](https://www.wis-tns.org/search?ra=261.940809&decl=-14.528327&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=261.940809&dec=-14.528327&layer=ls-dr10&zoom=16&mark=261.940809,-14.528327) | | | |
| 6 | `ZTF25aamhewc` | [ALeRCE](https://alerce.online/object/ZTF25aamhewc) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamhewc/) · [Fink](https://fink-portal.org/ZTF25aamhewc) · [TNS cone 5″](https://www.wis-tns.org/search?ra=283.811500&decl=-17.369957&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=283.811500&dec=-17.369957&layer=ls-dr10&zoom=16&mark=283.811500,-17.369957) | | | |
| 7 | `ZTF25aamimsl` | [ALeRCE](https://alerce.online/object/ZTF25aamimsl) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamimsl/) · [Fink](https://fink-portal.org/ZTF25aamimsl) · [TNS cone 5″](https://www.wis-tns.org/search?ra=141.000011&decl=11.504822&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=141.000011&dec=11.504822&layer=ls-dr10&zoom=16&mark=141.000011,11.504822) | | | |
| 8 | `ZTF25aamioam` | [ALeRCE](https://alerce.online/object/ZTF25aamioam) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamioam/) · [Fink](https://fink-portal.org/ZTF25aamioam) · [TNS cone 5″](https://www.wis-tns.org/search?ra=149.287219&decl=10.443462&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=149.287219&dec=10.443462&layer=ls-dr10&zoom=16&mark=149.287219,10.443462) | | | |
| 9 | `ZTF25aamitsb` | [ALeRCE](https://alerce.online/object/ZTF25aamitsb) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamitsb/) · [Fink](https://fink-portal.org/ZTF25aamitsb) · [TNS cone 5″](https://www.wis-tns.org/search?ra=144.138922&decl=10.647984&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=144.138922&dec=10.647984&layer=ls-dr10&zoom=16&mark=144.138922,10.647984) | | | |
| 10 | `ZTF25aamjaji` | [ALeRCE](https://alerce.online/object/ZTF25aamjaji) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamjaji/) · [Fink](https://fink-portal.org/ZTF25aamjaji) · [TNS cone 5″](https://www.wis-tns.org/search?ra=150.829574&decl=22.475737&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=150.829574&dec=22.475737&layer=ls-dr10&zoom=16&mark=150.829574,22.475737) | | | |
| 11 | `ZTF25aamjata` | [ALeRCE](https://alerce.online/object/ZTF25aamjata) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamjata/) · [Fink](https://fink-portal.org/ZTF25aamjata) · [TNS cone 5″](https://www.wis-tns.org/search?ra=148.362548&decl=17.215705&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=148.362548&dec=17.215705&layer=ls-dr10&zoom=16&mark=148.362548,17.215705) | | | |
| 12 | `ZTF25aamkbbd` | [ALeRCE](https://alerce.online/object/ZTF25aamkbbd) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamkbbd/) · [Fink](https://fink-portal.org/ZTF25aamkbbd) · [TNS cone 5″](https://www.wis-tns.org/search?ra=209.538559&decl=1.543079&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=209.538559&dec=1.543079&layer=ls-dr10&zoom=16&mark=209.538559,1.543079) | | | |
| 13 | `ZTF25aamkldj` | [ALeRCE](https://alerce.online/object/ZTF25aamkldj) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamkldj/) · [Fink](https://fink-portal.org/ZTF25aamkldj) · [TNS cone 5″](https://www.wis-tns.org/search?ra=253.178490&decl=-8.415333&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=253.178490&dec=-8.415333&layer=ls-dr10&zoom=16&mark=253.178490,-8.415333) | | | |
| 14 | `ZTF25aampiuq` | [ALeRCE](https://alerce.online/object/ZTF25aampiuq) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aampiuq/) · [Fink](https://fink-portal.org/ZTF25aampiuq) · [TNS cone 5″](https://www.wis-tns.org/search?ra=134.068865&decl=15.438669&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=134.068865&dec=15.438669&layer=ls-dr10&zoom=16&mark=134.068865,15.438669) | | | |
| 15 | `ZTF25aamppsd` | [ALeRCE](https://alerce.online/object/ZTF25aamppsd) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamppsd/) · [Fink](https://fink-portal.org/ZTF25aamppsd) · [TNS cone 5″](https://www.wis-tns.org/search?ra=156.678234&decl=8.089130&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=156.678234&dec=8.089130&layer=ls-dr10&zoom=16&mark=156.678234,8.089130) | | | |
| 16 | `ZTF25aamqlzp` | [ALeRCE](https://alerce.online/object/ZTF25aamqlzp) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aamqlzp/) · [Fink](https://fink-portal.org/ZTF25aamqlzp) · [TNS cone 5″](https://www.wis-tns.org/search?ra=252.546849&decl=-19.801183&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=252.546849&dec=-19.801183&layer=ls-dr10&zoom=16&mark=252.546849,-19.801183) | | | |
| 17 | `ZTF25aanbdmw` | [ALeRCE](https://alerce.online/object/ZTF25aanbdmw) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanbdmw/) · [Fink](https://fink-portal.org/ZTF25aanbdmw) · [TNS cone 5″](https://www.wis-tns.org/search?ra=147.825948&decl=8.982186&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=147.825948&dec=8.982186&layer=ls-dr10&zoom=16&mark=147.825948,8.982186) | | | |
| 18 | `ZTF25aanbhgp` | [ALeRCE](https://alerce.online/object/ZTF25aanbhgp) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanbhgp/) · [Fink](https://fink-portal.org/ZTF25aanbhgp) · [TNS cone 5″](https://www.wis-tns.org/search?ra=146.119587&decl=3.919159&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=146.119587&dec=3.919159&layer=ls-dr10&zoom=16&mark=146.119587,3.919159) | | | |
| 19 | `ZTF25aanbhlb` | [ALeRCE](https://alerce.online/object/ZTF25aanbhlb) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanbhlb/) · [Fink](https://fink-portal.org/ZTF25aanbhlb) · [TNS cone 5″](https://www.wis-tns.org/search?ra=150.522886&decl=17.878053&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=150.522886&dec=17.878053&layer=ls-dr10&zoom=16&mark=150.522886,17.878053) | | | |
| 20 | `ZTF25aanbpxg` | [ALeRCE](https://alerce.online/object/ZTF25aanbpxg) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanbpxg/) · [Fink](https://fink-portal.org/ZTF25aanbpxg) · [TNS cone 5″](https://www.wis-tns.org/search?ra=148.011913&decl=6.795770&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=148.011913&dec=6.795770&layer=ls-dr10&zoom=16&mark=148.011913,6.795770) | | | |
| 21 | `ZTF25aancvre` | [ALeRCE](https://alerce.online/object/ZTF25aancvre) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aancvre/) · [Fink](https://fink-portal.org/ZTF25aancvre) · [TNS cone 5″](https://www.wis-tns.org/search?ra=251.971046&decl=-14.864622&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=251.971046&dec=-14.864622&layer=ls-dr10&zoom=16&mark=251.971046,-14.864622) | | | |
| 22 | `ZTF25aanevqm` | [ALeRCE](https://alerce.online/object/ZTF25aanevqm) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanevqm/) · [Fink](https://fink-portal.org/ZTF25aanevqm) · [TNS cone 5″](https://www.wis-tns.org/search?ra=139.508489&decl=5.196097&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=139.508489&dec=5.196097&layer=ls-dr10&zoom=16&mark=139.508489,5.196097) | | | |
| 23 | `ZTF25aanfhfi` | [ALeRCE](https://alerce.online/object/ZTF25aanfhfi) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanfhfi/) · [Fink](https://fink-portal.org/ZTF25aanfhfi) · [TNS cone 5″](https://www.wis-tns.org/search?ra=154.496235&decl=13.458050&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=154.496235&dec=13.458050&layer=ls-dr10&zoom=16&mark=154.496235,13.458050) | | | |
| 24 | `ZTF25aanijcp` | [ALeRCE](https://alerce.online/object/ZTF25aanijcp) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanijcp/) · [Fink](https://fink-portal.org/ZTF25aanijcp) · [TNS cone 5″](https://www.wis-tns.org/search?ra=120.955713&decl=-2.980057&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=120.955713&dec=-2.980057&layer=ls-dr10&zoom=16&mark=120.955713,-2.980057) | | | |
| 25 | `ZTF25aanijgt` | [ALeRCE](https://alerce.online/object/ZTF25aanijgt) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanijgt/) · [Fink](https://fink-portal.org/ZTF25aanijgt) · [TNS cone 5″](https://www.wis-tns.org/search?ra=125.891006&decl=-20.587868&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=125.891006&dec=-20.587868&layer=ls-dr10&zoom=16&mark=125.891006,-20.587868) | | | |
| 26 | `ZTF25aanktst` | [ALeRCE](https://alerce.online/object/ZTF25aanktst) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanktst/) · [Fink](https://fink-portal.org/ZTF25aanktst) · [TNS cone 5″](https://www.wis-tns.org/search?ra=226.008207&decl=-27.829859&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=226.008207&dec=-27.829859&layer=ls-dr10&zoom=16&mark=226.008207,-27.829859) | | | |
| 27 | `ZTF25aanmiqt` | [ALeRCE](https://alerce.online/object/ZTF25aanmiqt) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanmiqt/) · [Fink](https://fink-portal.org/ZTF25aanmiqt) · [TNS cone 5″](https://www.wis-tns.org/search?ra=297.875789&decl=12.554716&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=297.875789&dec=12.554716&layer=ls-dr10&zoom=16&mark=297.875789,12.554716) | | | |
| 28 | `ZTF25aanwywg` | [ALeRCE](https://alerce.online/object/ZTF25aanwywg) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanwywg/) · [Fink](https://fink-portal.org/ZTF25aanwywg) · [TNS cone 5″](https://www.wis-tns.org/search?ra=264.607005&decl=-2.865489&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=264.607005&dec=-2.865489&layer=ls-dr10&zoom=16&mark=264.607005,-2.865489) | | | |
| 29 | `ZTF25aanycov` | [ALeRCE](https://alerce.online/object/ZTF25aanycov) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanycov/) · [Fink](https://fink-portal.org/ZTF25aanycov) · [TNS cone 5″](https://www.wis-tns.org/search?ra=258.995668&decl=-13.968282&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=258.995668&dec=-13.968282&layer=ls-dr10&zoom=16&mark=258.995668,-13.968282) | | | |
| 30 | `ZTF25aanzoqu` | [ALeRCE](https://alerce.online/object/ZTF25aanzoqu) · [Lasair](https://lasair-ztf.lsst.ac.uk/objects/ZTF25aanzoqu/) · [Fink](https://fink-portal.org/ZTF25aanzoqu) · [TNS cone 5″](https://www.wis-tns.org/search?ra=264.702558&decl=-9.132227&radius=5&coords_unit=arcsec) · [Legacy Survey](https://www.legacysurvey.org/viewer?ra=264.702558&dec=-9.132227&layer=ls-dr10&zoom=16&mark=264.702558,-9.132227) | | | |

**Tally (owner):** genuine-looking SNe: ___ / 30 · unsure: ___ · outcome: keep rule / tighten rule

## Stratification of all contaminants (§6.4 (b))

Strata are computed at each object's first pool night t from data known at t (history age, Fink crossmatch, offset from ALeRCE `distnr`), plus static Sherlock context from Lasair. Sherlock status: ok.

**Alert-time history age (t − first detection incl. per-alert i:jdstarthist)**

| Stratum | Contaminants | Share |
|---|---|---|
| 7–14 d | 22 | 44% |
| 3–7 d | 16 | 32% |
| 0–3 d | 12 | 24% |

**Fink alert-time SIMBAD crossmatch (d:cdsxmatch, grouped)**

| Stratum | Contaminants | Share |
|---|---|---|
| no SIMBAD match | 49 | 98% |
| other (Fail 503) | 1 | 2% |

**Sherlock classification (Lasair)**

| Stratum | Contaminants | Share |
|---|---|---|
| (no row) | 37 | 74% |
| SN | 8 | 16% |
| ORPHAN | 4 | 8% |
| BS | 1 | 2% |

**Offset from host / nearest reference source (Sherlock separation, else ALeRCE distnr)**

| Stratum | Contaminants | Share |
|---|---|---|
| > 2″ | 44 | 88% |
| < 0.5″ (nuclear) | 5 | 10% |
| 0.5–2″ | 1 | 2% |

**Known solar-system object at the position (alert-packet ssdistnr ≤ 12″, ALeRCE ss_ztf)**

| Stratum | Contaminants | Share |
|---|---|---|
| known asteroid within 12″ (alert packet) | 28 | 56% |
| no known asteroid match | 22 | 44% |

**Sherlock class × offset**

| Sherlock | Offset | n |
|---|---|---|
| (no row) | > 2″ | 37 |
| SN | > 2″ | 7 |
| ORPHAN | < 0.5″ (nuclear) | 4 |
| SN | < 0.5″ (nuclear) | 1 |
| BS | 0.5–2″ | 1 |

## Context for the sampled objects (open after judging)

<details><summary>Show machine context</summary>

| # | OID | Pool nights | Qual. peak | Age at t (d) | Fink xmatch | Sherlock | Host z | Offset (src) | Known asteroid |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `ZTF25aalvose` | 2 | 17.44 | 12.4 | Unknown | (no row) | — | 4.65″ (alerce distnr) | 33807 (0.0″) |
| 2 | `ZTF25aalvpuf` | 2 | 18.30 | 12.4 | Unknown | SN | 0.000 | 4.76″ (sherlock) | — |
| 3 | `ZTF25aalzdap` | 3 | 17.17 | 11.5 | Unknown | ORPHAN | 0.000 | 0.00″ (sherlock) | — |
| 4 | `ZTF25aamaxbv` | 1 | 17.20 | 13.4 | Unknown | SN | 0.000 | 4.78″ (sherlock) | — |
| 5 | `ZTF25aamhede` | 4 | 17.06 | 10.4 | Unknown | (no row) | — | 3.67″ (alerce distnr) | — |
| 6 | `ZTF25aamhewc` | 4 | 18.42 | 10.4 | Unknown | SN | 0.000 | 2.33″ (sherlock) | — |
| 7 | `ZTF25aamimsl` | 5 | 17.65 | 9.7 | Unknown | (no row) | — | 7.56″ (alerce distnr) | — |
| 8 | `ZTF25aamioam` | 5 | 16.90 | 9.7 | Unknown | (no row) | — | 5.77″ (alerce distnr) | — |
| 9 | `ZTF25aamitsb` | 5 | 17.69 | 9.7 | Unknown | (no row) | — | 6.62″ (alerce distnr) | — |
| 10 | `ZTF25aamjaji` | 5 | 17.57 | 9.6 | Unknown | (no row) | — | 9.70″ (alerce distnr) | — |
| 11 | `ZTF25aamjata` | 5 | 18.01 | 9.6 | Unknown | (no row) | — | 12.57″ (alerce distnr) | — |
| 12 | `ZTF25aamkbbd` | 4 | 18.43 | 10.4 | Unknown | (no row) | — | 7.62″ (alerce distnr) | — |
| 13 | `ZTF25aamkldj` | 5 | 17.06 | 9.4 | Unknown | (no row) | — | 9.16″ (alerce distnr) | 14494 (0.0″) |
| 14 | `ZTF25aampiuq` | 5 | 18.44 | 8.6 | Unknown | (no row) | — | 10.87″ (alerce distnr) | 13182 (0.0″) |
| 15 | `ZTF25aamppsd` | 5 | 17.64 | 8.5 | Unknown | (no row) | — | 7.46″ (alerce distnr) | 10775 (0.0″) |
| 16 | `ZTF25aamqlzp` | 5 | 16.51 | 8.4 | Unknown | (no row) | — | 5.95″ (alerce distnr) | 5296 (0.0″) |
| 17 | `ZTF25aanbdmw` | 5 | 17.37 | 4.6 | Unknown | (no row) | — | 6.99″ (alerce distnr) | 5034 (0.0″) |
| 18 | `ZTF25aanbhgp` | 5 | 18.34 | 4.6 | Unknown | (no row) | — | 9.58″ (alerce distnr) | 61197 (0.0″) |
| 19 | `ZTF25aanbhlb` | 5 | 18.41 | 4.6 | Unknown | (no row) | — | 12.15″ (alerce distnr) | 16234 (0.0″) |
| 20 | `ZTF25aanbpxg` | 5 | 18.50 | 4.6 | Unknown | (no row) | — | 2.15″ (alerce distnr) | 12053 (0.0″) |
| 21 | `ZTF25aancvre` | 4 | 18.32 | 5.5 | Unknown | ORPHAN | 0.000 | 0.00″ (sherlock) | — |
| 22 | `ZTF25aanevqm` | 5 | 18.49 | 3.6 | Unknown | (no row) | — | 5.94″ (alerce distnr) | 20729 (0.0″) |
| 23 | `ZTF25aanfhfi` | 5 | 18.19 | 3.6 | Unknown | (no row) | — | 11.66″ (alerce distnr) | 15942 (0.0″) |
| 24 | `ZTF25aanijcp` | 4 | 18.00 | 0.7 | Unknown | ORPHAN | 0.000 | 0.00″ (sherlock) | — |
| 25 | `ZTF25aanijgt` | 2 | 17.94 | 2.7 | Unknown | SN | 0.000 | 27.88″ (sherlock) | — |
| 26 | `ZTF25aanktst` | 2 | 17.86 | 2.5 | Unknown | ORPHAN | 0.000 | 0.00″ (sherlock) | — |
| 27 | `ZTF25aanmiqt` | 2 | 16.78 | 2.4 | Unknown | SN | 0.000 | 5.97″ (sherlock) | — |
| 28 | `ZTF25aanwywg` | 2 | 17.64 | 0.5 | Unknown | SN | 0.000 | 11.97″ (sherlock) | — |
| 29 | `ZTF25aanycov` | 2 | 17.12 | 0.4 | Unknown | (no row) | — | 7.99″ (alerce distnr) | 13086 (0.0″) |
| 30 | `ZTF25aanzoqu` | 2 | 17.47 | 0.4 | Unknown | (no row) | — | 3.20″ (alerce distnr) | 32221 (0.0″) |

</details>

