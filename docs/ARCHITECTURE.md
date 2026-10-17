# Cosmic Triage — Architecture v1 (authoritative)

*Consolidated 2026-10-17 from v0, Review-01 addendum, and Review-02. This is the single source of truth for implementation. `REVIEW-01-addendum.md` and `REVIEW-02.md` are rationale and history; where they differ from this document, this document wins. No code exists yet; implementation begins only after approval.*

---

## 0. One-paragraph summary

Cosmic Triage is a **learning-first, rigorously evaluated AI system** that decides which astronomical transients deserve limited follow-up observations. Its scientific substrate — calibrated beliefs about each candidate, an explicit objective-conditioned reward, a constraint-solving nightly scheduler, and a leakage-safe historical replay against ZTF Bright Transient Survey ground truth — exists to make one AI-engineering question answerable with numbers: **does a grounded, budgeted, tool-using LLM Investigator, whose typed and provenance-backed claims are validated before they touch a Bayesian decision, measurably improve follow-up decisions, at what cost, and where does it fail?** The project is ~65% LLM/agent engineering (orchestration, tools, retrieval, state, routing/cascades, grounding, failure recovery, evaluation) and ~35% scientific substrate (probability, optimization, replay). It reproduces established ideas (REFITT's ORACLE framing, BTSbot's policy, AAS2RTO's scoring, RESSPECT's cost model) as baselines and claims no scientific novelty.

---

## 1. Problem definition

### 1.1 Setting and users
One researcher (you) acting as PI of a small follow-up program with one modeled facility for N nights, choosing nightly which ZTF candidates to observe. Objectives are explicit and switchable:
- **O1 Cosmology-grade SNe Ia:** classification spectra of normal SNe Ia *before peak*.
- **O2 Core-collapse diversity:** classify stripped-envelope / Type II SNe as early as possible.
- **O3 Rare-object hunt:** TDEs, SLSNe, Ca-rich, anomalies; high false-alarm tolerance (later milestone; non-additive reward).
- **O4 Completeness:** classify everything brighter than m — BTS's mandate; the natural comparison to practice.

### 1.2 The decision loop (per night t)
1. **Belief** b_i(t): posterior over coarse classes K = {Ia, II, Ibc, other-luminous (SLSN/TDE), contaminant (AGN/CV/star/bogus)} for each candidate in the forward pool, from calibrated, pooled evidence channels.
2. **Investigate** (gated): for candidates where it may matter, the Investigator gathers context (reports, catalogs, images, literature) through typed tools and emits validated claims with code-owned effects on reward and belief.
3. **Value**: terminal actions (classification spectra) are priced by **direct expected reward** E_{c∼b}[R(objective, c, phase)]; information actions (*wait*, targeted photometry) by **one-step EVSI** against tomorrow's allocation. EIG is displayed as a diagnostic only.
4. **Schedule**: CP-SAT over visibility windows, exposure times, overheads, Moon/altitude limits, and a **binding** budget.
5. **Replay**: outcomes revealed from history; beliefs and ledgers updated; metrics accumulated; next night.

### 1.3 Boundaries
In scope: ZTF public alerts via brokers; extragalactic transients and contaminants; one facility (extensible); nightly replanning; replay evaluation; the Investigator over public dated corpora. Out of scope initially: multi-messenger tiling, real telescope control, Rubin-scale throughput, agent-written code execution, LLM-generated priors. Explicitly simulated (and labeled): spectrum *outcomes* when they feed later beliefs, weather beyond the ZTF record, photometry at times ZTF didn't observe.

### 1.4 Governing rule
**Hypotheses are generated; probabilities are computed.** LLMs may propose, retrieve, extract, and explain. No LLM output becomes evidence except as a typed `Claim` that passed deterministic validators and maps to a pre-registered, code-owned effect. Code owns control flow, budgets, thresholds, and all arithmetic.

---

## 2. Verified research findings

### 2.1 What exists and how good it is
| Layer | State of the art | Our stance |
|---|---|---|
| Detection, alert distribution | ZTF public stream; Rubin alerts public via 7 brokers (2026); ZTF funded through end-2026 | Consume |
| Real/bogus, early typing | ALeRCE stamp classifier (first alert); BTSbot (CNN on triplets + 25 features; 93% deployment purity; public weights) | Prior channel; BTSbot is a baseline |
| Light-curve classification | ALeRCE hierarchical RF (current-state only); Fink per-alert SuperNNova/RF scores | Fink per-alert = replay-safe channel |
| Candidate characterization (context) | **Human scanners** (BTS II §2.2): catalog cross-matches, AGN/WISE checks, star counterparts, prior flares, TNS duplication check, host redshift | **The Investigator's job** |
| Visibility | astropy/astroplan | Use |
| Scheduling | LCO ILP (OR-Tools), ZTF/Rubin survey schedulers, LUMOS MILP, astroplan greedy | CP-SAT, small |
| Follow-up prioritization | BTSbot rules; AAS2RTO multiplicative score, greedy; REFITT forecast-uncertainty recommendations (photometry, simulation-only); RESSPECT/Fink AL (training-set value, knapsack budget, 92 real spectra) | All become baselines; see `REVIEW-02.md` §B for the full comparison |
| LLMs in transient astronomy | RADAR (LLM parsing of GCN circulars → VLA blocks; F₁ 0.89), ALeRCE text-to-SQL, AstroAlertBench (LLM alert classification; honesty/calibration gaps) | Closest prior art for the agent layer; none evaluates decision impact under replay |

### 2.2 Data and API inventory (status as verified 2026-10-17)
| Resource | Status | Auth | Use | Caveats |
|---|---|---|---|---|
| ALeRCE ZTF API `api.alerce.online/ztf/v1` | ✅ live, fresh to 2026-10-16 | none | forward pool (`/objects?firstmjd…`), light curves incl. non-detections, stamp-class prior, stamps for multimodal | `lc_classifier` probabilities are current-state → never used in replay; `/objects` class/probability filter quirk to check |
| Fink ZTF API `api.ztf.fink-portal.org` | docs verified; POST untested | none | one row per alert with alert-time scores (`d:rf_snia_vs_nonia`, `d:snn_*`, `d:cdsxmatch`, `d:tns`), upper limits via `withupperlim` | module versions drift; verify in M0 |
| Lasair | docs verified | free token | SQL queries, object light curves with upper limits, **Sherlock** host context, TNS crossmatch table | 100 calls/h standard tier |
| BTS Sample Explorer CSV | ✅ live | none | ground truth: `ZTFID, IAUID, …, peakt, peakmag, type, redshift` | pull **without** quality/purity filters to get the full saved list incl. unclassified; lacks classification *date* |
| TNS | docs verified | bot key | report/classification dates (gold for prior-classification claims) | individual bot creation unverified → M0; fallback Lasair/Fink TNS tables |
| ZTF public alert archive | ✅ live (2025-01-01 → 2026-10-16) | none | gold replay (Avro with `prv_candidates`, cutouts) for a few nights; night-level weather proxy via file size | 5–20 GB/night |
| SIMBAD / NED / Gaia / WISE / PS1 via astroquery | standard | none | Investigator catalog tools | rate limits; cache everything |
| AstroNotes, ATels, GCN circulars, arXiv/ADS abstracts | public, dated | none / free ADS token | Investigator text corpora with **as-of** filtering | ingestion and indexing effort; ATels sparse for SNe post-2020 |
| `btsbot` (pip, HF weights) | public | none | triage + multimodal baseline | GPU optional |
| sncosmo (SALT3, Vincenzi+19 CC templates, ZTF bands) | mature | none | template-fit **tool**; full likelihood channel in M7 | template downloads; TDE/SLSN coverage thin |
| ELAsTiCC2 | public | none | optional simulation fallback | not needed early |

### 2.3 Jev (TypeSafe) — facts that constrain design
Official docs: `docs.typesafe.ai`; OpenRouter guide. Versions jev-1.13 (text) / jev-1.14 (text+images, 2026-10-14); alias `jev-latest`. Primitives `Choice` (≤255 options), `Score` (2–10 levels), `Noul`, `Box` (1.14). Many independent questions per call. $0.042/M input tokens, output free; independent p50 ≈ 175–185 ms. Confidence formulas are published; calibration is a training objective, not a guarantee — thresholds must be fit per domain. Documented weaknesses: counting, numeric comparison, dates, Score interpolation, first-option bias, literal reading, distraction by irrelevant state, adversarial state. Vendor's suitability test: deciding not generating; predefined answer space; one focused judgement; info in state; expert could judge in ~5 s; software consumes result. **Consequence:** Jev never touches light-curve numbers, EIG, or scheduling; it is used only for bounded semantic judgements over pre-structured state (§5).

### 2.4 Domain primer (what you'll learn in M1)
After a first detection you know position, a few g/r magnitudes, offset from catalogued sources, and real/bogus scores; you do not know class, distance/luminosity, phase, reddening, or whether it is nuclear. Scanners decide using brightness (SEDM classifies to ~18.5 mag in ~30 min; 2100 s for an 18.5-mag SN II), SN-like rise, extragalactic context, visibility, and whether someone else already classified it. A spectrum resolves class/redshift/phase in one shot but is expensive and brightness-limited; photometry is cheap but rarely decisive early; waiting for free survey points has option value; phase matters (pre-peak Ia for cosmology). Even spectroscopic "truth" is noisy (SNID/NGSF/DASH agree with humans 79/88/76% on 4,646 SEDM spectra).

---

## 3. Architecture

### 3.1 Component diagram
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          Observatory Console (React/TS)                          │
│ candidates · light curves · belief by channel · investigation trace · ledger ·   │
│ night plan (Gantt) · constraint toggles · policy/agent diff · replay scrubber ·   │
│ cascade dial · simulation badges · concept cards                                 │
└───────────────▲───────────────────────────────▲──────────────────────────────────┘
                │ typed JSON (pydantic → TS)    │ SSE replay ticks / trace stream
┌───────────────┴───────────────────────────────┴──────────────────────────────────┐
│                                  api (FastAPI)                                   │
└──┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬─────┘
   │              │              │              │              │              │
┌──▼─────┐  ┌─────▼──────┐  ┌────▼─────┐  ┌─────▼─────┐  ┌─────▼──────┐  ┌────▼────┐
│ingest  │  │ belief     │  │ value    │  │ schedule  │  │ replay     │  │metrics  │
│brokers,│  │ channels → │  │ reward   │  │ astroplan │  │ clock,     │  │tiers A/B│
│BTS,    │  │ calibrate →│  │ tables,  │  │ windows → │  │ snapshot,  │  │/C, L0–3 │
│corpora,│  │ learned    │  │ EVSI,    │  │ CP-SAT,   │  │ outcome    │  │ladder,  │
│cache   │  │ pool       │  │ claim    │  │ checker   │  │ reveal,    │  │CIs      │
│        │  │            │  │ effects  │  │           │  │ policies   │  │         │
└──▲─────┘  └─────▲──────┘  └────▲─────┘  └─────▲─────┘  └─────▲──────┘  └────▲────┘
   │              │              │              │              │              │
   └──────────────┴──────────────┴──────┬───────┴──────────────┴──────────────┘
                                        │
                        ┌───────────────▼────────────────┐
                        │ contracts (pydantic v2, versioned)│
                        │ Candidate · PhotometryPoint ·    │
                        │ Snapshot · Belief · Objective ·  │
                        │ Action · Schedule · Outcome ·    │
                        │ Evidence · Claim · Ledger ·      │
                        │ Trace · DecisionTrace            │
                        └───────────────▲────────────────┘
                                        │
┌───────────────────────────────────────┴───────────────────────────────────────────┐
│                              Investigator (the AI core)                           │
│  gate ─► plan ─► act (tool registry, as-of filter, cache, retries, budget) ─►      │
│  extract (LLM → Claim drafts) ─► validate (deterministic + Jev support) ─► ledger  │
│  slots: gate {Jev Noul | entropy | always}  plan {LLM | Jev Choice | fixed}        │
│         extract {Haiku→Sonnet cascade | Sonnet}  verify {Jev | Claude-judge | det.}│
│  memory: per-candidate EvidenceLedger, compaction, staleness                        │
│  observability: spans, model ids, tokens, $, validator outcomes → runs/*.jsonl      │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Responsibilities
- `ingest` — HTTP, caching (parquet/duckdb), corpus indexing with dates; no science.
- `belief` — channels → per-channel calibration → learned log-linear pool; phase/peak estimate; emits `Belief` with per-channel contributions. Channels are **partitioned by raw evidence** to prevent double counting: photometry → (M1: Fink per-alert scores; M7: template likelihoods), stamps → ALeRCE stamp class / BTSbot, history → contaminant feature model, context → Investigator claims (via code-owned effects) and scanner.
- `value` — reward tables R(objective, class, phase_bin), frozen and versioned; direct expected reward for terminal actions; one-step EVSI for *wait*/photometry; applies `Claim` effects (e.g., prior classification → spectrum reward 0).
- `schedule` — visibility intervals, exposure model (SEDM-derived), CP-SAT interval model with no-overlap and budget; independent feasibility checker.
- `replay` — the only module that may read anything with a future timestamp; constructs `Snapshot(t)`; reveals outcomes; runs policies; weather from the ZTF record (+ seeded downtime).
- `investigator` — §4.
- `metrics` — Tier A/B/C, simulation ladder labels, bootstrap CIs over nights and candidates.
- `api`/`console` — presentation only; reads traces and runs.

### 3.3 Data flow for one replay night
1. `replay.Clock` builds `Snapshot(t)`: forward pool (ALeRCE objects with first detection in [t−14, t] passing a time-honest pre-filter), photometry ≤ t, Fink rows ≤ t, static context; denylist strips `type, redshift, peak*, class, probability, ndethist/ncovhist-final`.
2. `belief` computes b_i(t) from allowed channels.
3. Gate selects candidates for the Investigator (budgeted); runs produce `Claim`s and traces; ledgers persist across nights.
4. `value` prices actions incl. claim effects; `schedule` solves; checker verifies.
5. `replay` executes: spectrum → reward from truth (L0) and, for subsequent-night beliefs, a confusion-model reveal (L2); photometry → real next ZTF point if present, else posterior-predictive draw flagged `simulated` (L3).
6. `metrics` accumulate; `DecisionTrace` per candidate per night is written.

---

## 4. The Investigator

### 4.1 Capabilities (bounded) — see `REVIEW-02.md` §A for the full table
1. **Prior-report & classification lookup** (TNS/AstroNotes/ATels/GCNs, as-of t) → `Claim{prior_classification}` → spectrum reward 0 / reduced; class likelihood via a confusion prior.
2. **Host & context resolution** (SIMBAD, NED, Sherlock, Gaia, WISE, PS1) → `Claim{host_redshift | known_agn | star_counterpart | prior_flares | nuclear}` → absolute-magnitude constraint / contaminant prior / TDE-AGN weighting.
3. **Ambiguity investigation** (gated on entropy or poor fits) → chooses among registered analysis tools (template fit for an alternative class, color evolution, rise rate, host offset, dust) → numeric outputs enter the pool as channels; the narrative does not.
4. **Hypothesis comparison & dossier** → console only; every sentence cites ledger ids; Jev `Noul` support check; unsupported sentences dropped and counted.
5. **Literature grounding** (arXiv/ADS abstracts) → may propose tests and *named* hypotheses; may not set numeric priors.
6. **Image reading** (cutout triplets, Jev-1.14 / Claude vision) → typed `Choice` → pool channel only if it wins the M6 ablation against `btsbot`.

### 4.2 Run loop (code-owned)
`gate → plan → act → extract → validate → ledger → stop?` with hard budgets (tool calls, tokens, $, wall time) and stop conditions (budget, no new information, resolved). Each of `gate`, `plan`, `extract`, `verify` is a slot with ≥ 2 implementations so every architectural choice is an ablation with a baseline.

### 4.3 Contracts (abbreviated)
```python
class Evidence(BaseModel):
    id: str; source: Literal["tns","astronote","atel","gcn","simbad","ned","sherlock","gaia","wise","ps1","alerce","fink","arxiv","cutout","tool"]
    source_date: float | None          # MJD of the record itself; None for static catalogs
    retrieved_at_sim_time: float        # t of the run
    query: dict; raw_excerpt_hash: str; parsed: dict

class Claim(BaseModel):
    kind: Literal["prior_classification","host_redshift","known_agn","star_counterpart","prior_flares","nuclear","analysis_result"]
    payload: dict; evidence_ids: list[str]; extractor_model: str
    validation: ValidationReport        # schema, provenance-exists, date<=t, type-specific, support score

class EvidenceLedger(BaseModel):
    oid: str; entries: list[Evidence]; claims: list[Claim]; compactions: list[Compaction]; version: str

class Trace(BaseModel):                  # one per run; read by the console
    run_id: str; oid: str; t_mjd: float; config_version: str; spans: list[Span]; cost_usd: float; model_ids: dict[str,str]
```

### 4.4 Validation and provenance
A claim is accepted iff: schema-valid; every `evidence_id` exists in this run's ledger; every cited `source_date ≤ t` (**hard leakage check**); type-specific checks pass (code recomputes separations from source coordinates; z ∈ [0, 3]; report type ∈ {discovery, classification}); support verification ≥ τ (Jev `Noul` / Claude-judge / deterministic-only per config). Rejections are logged with reasons and reported.

### 4.5 Memory, context, failure recovery, observability
- **Memory:** ledger persists across nights; compaction summaries cite ids and never replace raw; staleness policy per source (reports re-queried nightly, catalogs never). Memory on/off is an ablation.
- **Context:** packs assembled by code under token budgets (2k/8k/32k sweep); relevance by Jev `Score` vs BM25 vs recency; evidence cards present numbers as labeled fields.
- **Failure recovery:** typed tool errors; retries with backoff + jitter; per-tool circuit breakers; partial runs valid and marked; idempotent re-runs keyed by `(oid, t, config_version)`; chaos flags per tool for injection tests.
- **Observability:** spans for every tool and model call with resolved model ids, prompt/response hashes, tokens, $; JSONL under `runs/`; the console reads it directly.

---

## 5. Jev — exactly where, with baselines
| Role | Primitive | Baseline(s) | Verdict metric |
|---|---|---|---|
| Investigation gate | `Noul("worth investigating given objective & belief summary")` | entropy threshold; always | Tier-B gain per $ |
| Tool router | `Choice(next_tool | ledger state)` | LLM planner; fixed order | resolution rate, cost |
| Claim-support verifier | `Noul("excerpt supports claim")` | Claude-judge; deterministic-only | catch rate on corrupted claims; false-reject rate |
| Context relevance | `Score(relevance)` | BM25; recency | Tier-A accuracy at fixed budget |
| Scanner (secondary) | `Choice`/`Score` over evidence card (context-only vs full) | GBM on same features; BTSbot; Fink scores; Claude structured | pool weight; calibration |
Operational rules: randomize `Choice` option order and report flip rate; pin model version and log resolved id; calibrate Jev outputs before any pooling; never use Jev for arithmetic, dates, or counting.

---

## 6. Scientific substrate (minimal, credible)

### 6.1 Beliefs
M1: channels = Fink per-alert scores (photometry), ALeRCE stamp class (first alert), contaminant feature model (history), each temperature-scaled on training nights; pooled by L2-regularized multinomial logistic regression on log-probs; coarse K; ECE/log-loss gate — a configuration less calibrated than the best single channel is excluded from policy comparisons. M7: sncosmo template likelihoods (precomputed per-template ZTF-band grids; censored likelihood for upper limits) as an additional channel.

### 6.2 Value
Reward tables R(objective, class, phase_bin) hand-written, versioned, frozen before comparisons. Terminal: E_{c∼b}[R]. Information: EVSI₁ = E_y[V_{t+1}(b′(y))] − V_{t+1}(b) with V_{t+1} ≈ tomorrow's myopic allocation over posterior-predictive samples. EIG shown as a diagnostic. O3 needs diminishing-returns terms (piecewise-linear in CP-SAT) — later.

### 6.3 Schedule
Facility v1: Palomar site, SEDM-like spectrograph (exposure table from the SEDM paper, effective limit ≈ 18.5–19), overhead 300 s, min altitude 30°, Moon separation 30°; **budget chosen from pool statistics so that median(bright SN-like candidates)/(slots) ≥ 2** — if the sky doesn't supply enough, shrink the budget (3–4 spectra/night), never inflate the pool with unscoreable faint objects.

### 6.4 Replay integrity
Forward pool per night with a time-honest pre-filter mirroring the BTS alert filter (≥ 2 detections ≥ 30 min apart, drb ≥ 0.5, no star-like counterpart < 2″, no bright star < 20″, m ≤ 19, outside the Galactic plane); scoring only for peak ≤ 18.5; labels: BTS-saved-classified = class; BTS-saved-unclassified = **unknown**; never-saved & filter-passing & bright = **contaminant** (justified by BTS II's TNS audit: ~0.6% missed); unknowns reported under three treatments (0 / ALeRCE weak label / excluded). Strict temporal splits (rolling origin); broker classifier versions recorded and matched across train/eval; BTS catalog snapshotted by date. Weather: night-level from ZTF archive presence + seeded 10% downtime (L1 sensitivity).

### 6.5 Simulation-dependency ladder (every reported number carries one)
L0 none (real photometry, truth, geometry): calibration, Tier A, predicted-vs-realized EIG on real survey points, feasibility, **selection precision/recall-at-budget vs truth**. L1 parameterized physical models (exposure, magnitude limit, weather record + downtime): yield per spectrograph-hour, regret. L2 reveal noise (confusion matrix from the 4,646-spectra study; sensitivity 100/90/80%). L3 synthetic photometry (posterior-predictive draws): targeted-photometry policies, labeled "simulation study."

---

## 7. Evaluation plan

### 7.1 Policies compared on identical nights
random · brightest-first · broker-greedy × brightness × visibility (primary fair baseline) · AAS2RTO-like score · BTS-mimic (truth-correlated; caveated) · template-only/pool-only L0 (internal baseline) · **+Investigator** · +Jev gate/router/verifier variants · +cascade variants · oracle (regret bound).

### 7.2 Metrics
- **Substrate:** calibration (log-loss, Brier, ECE per epoch); selection precision/recall-at-budget; yield per spectrograph-hour; regret vs oracle; feasibility (0 violations); utilization; unknown-fraction per policy.
- **Investigator Tier A:** extraction precision/recall vs TNS/Lasair/BTS fields; grounding rate; **temporal leakage rate = 0** (a non-zero value is a bug); validator rejection distribution; human spot-check of 50 dossiers per milestone.
- **Tier B:** Δ calibration and Δ selection yield with vs without Investigator, stratified easy/ambiguous/contaminant; **wasted-spectrum rate** (spectra on objects already publicly classified at t); cost and latency per candidate and per night.
- **Tier C:** cost–quality frontiers across gate/planner/extractor/verifier variants, context budgets, memory on/off, tool subsets, parallel vs sequential, failure injection at 0/10/30% tool error rates; option-order flip rates.

### 7.3 Anti-circularity rules
No LLM-generated labels in any metric path. No LLM sees `type, redshift, peak*` or any post-t data. Reward tables frozen before comparisons. Simulated outcomes tagged and reported as a share. Training/calibration/pooling fit only on nights before the evaluation window.

### 7.4 Pre-registered verdicts
- Investigator stays in the live path for an objective only if Tier-B Δ yield > 0 with CI excluding 0 on the ambiguous/contaminant strata, or wasted-spectrum rate drops materially, at acceptable cost; otherwise it is reported as a measured null and kept as an ablation.
- Each Jev role is kept only if it beats its baseline on the stated metric at equal or lower cost.
- Image-LLM channel enters the pool only if its learned weight is non-zero with BTSbot present.

---

## 8. Observatory Console (learning instrument + demo)

### 8.1 Scientific dashboards
Views: sky & night (altitude tracks, Moon, twilight, time cursor) · candidate explorer (belief bars with evidence-by-channel, entropy, phase, expected reward per action) · light curve with upper limits and class bands · **investigation trace** (gate, tool calls with as-of dates/latency/cache/cost, claim drafts, validator verdicts, support scores, accepted claims with reward/belief deltas) · **evidence ledger browser** (dates relative to t; leakage badge that must never render) · plan Gantt with live constraint toggles and re-solve · **agent-vs-no-agent diff** and policy compare · replay scrubber · **cascade dial** with live cost–quality frontier · decision-trace drawer with "why not?" · simulation badges (L0–L3) on every number and point · concept cards (astronomy + probability + AI-engineering vocabulary) with Claude expansions verified by Jev.
Stack: FastAPI + SSE → React/TypeScript (Vite), Plotly, small D3 sky plot; types generated from pydantic. UI effort is time-boxed per milestone and always follows a measured result.

### 8.2 Night Theater — interactive simulation mode (first-class demo requirement)
A planetarium-style view in which a **historical observing night unfolds**: the sky as seen from the facility (alt-az dome projection with a real star catalog, horizon, Milky Way, Moon phase and position, twilight bands), the forward-pool candidates rising and setting as markers whose size/color encode belief and expected reward, the **simulated telescope's pointing reticle slewing between scheduled targets** with exposure arcs, real ZTF detections appearing at the moment they happened, and the **Investigator's decisions appearing as timeline events** (gate → tool calls → validated claims → reward deltas) with popovers into the trace. Controls: play/pause/scrub/speed, policy selector (and side-by-side A/B domes), objective switch, constraint toggles with live re-solve, "follow the telescope," and target close-ups via Aladin Lite (real survey imagery of the host) and the light curve.

**Grounding rules (binding):**
1. The Theater is a *player*, not a model. Every rendered element is driven from replay artifacts — `Schedule`, `DecisionTrace`, `Trace`, `Outcome`, and precomputed `NightFrame`s — never from UI-only logic. Positions (alt/az of candidates, Sun, Moon) are computed in Python with astropy and shipped as frames; the frontend only interpolates.
2. **Real vs simulated is always visible.** Real observations (ZTF detections, dated reports) render solid; the simulated facility and everything it "does" (pointing, exposures, reveals, seeded downtime, synthetic photometry) render in a distinct ghost/dashed style with the simulation-ladder badge (L1–L3). A persistent legend states: "Telescope and its observations are simulated; sky, candidates, detections, and reports are real."
3. Exploratory runs are watermarked `EXPLORATORY`; benchmark runs show their `run_id` and `config_hash`.
4. The Theater adds no scientific logic and cannot change a decision; it reads the same JSONL the metrics read.

**Phasing (so it never delays core engineering):**
| Phase | In milestone | Content |
|---|---|---|
| S0 | M1 (console v0) | Static alt-az dome for one night: horizon, Sun/Moon, twilight, pool candidates with altitude tracks, time cursor. Precomputed `NightFrame`s at 5-min cadence. |
| S1 | M3 | Night player: schedule executes over time — pointing reticle, slews, exposure arcs, weather/downtime state from the record, real detections appearing in time; L-badges and ghost styling. |
| S2 | M4 | Investigator events on the timeline with trace popovers; agent-vs-no-agent and policy A/B side-by-side domes. |
| S3 | M5+ | Polish: HYG star catalog + Milky Way + constellation lines, Aladin Lite close-ups, cinematic auto-tour of a night, cascade dial overlay, concept cards triggered by events (e.g., first slew → airmass card). |

Assets: HYG star database (public domain, bundled as static JSON ≤ 6th magnitude); Aladin Lite via its CDN at runtime (optional; degrade gracefully offline); Moon/Sun ephemerides from astropy on the backend.

---

## 9. Technology stack
Python 3.12 + `uv`; pydantic v2; httpx + disk cache → parquet/duckdb; numpy/scipy/scikit-learn (calibration, pooling); astropy/astroplan; sncosmo (tool; M7 channel); OR-Tools CP-SAT; `btsbot`; `typesafe-sdk` and/or OpenRouter for Jev; Anthropic SDK for Claude (Haiku/Sonnet/Opus); a small BM25 index for corpora (duckdb FTS or `rank_bm25`), embeddings optional later; pytest with recorded fixtures; ruff; FastAPI; React/TS/Vite/Plotly. Configs: versioned YAML for objectives, facilities, policies, investigator slots; `runs/` JSONL traces. Local-first; no services beyond the public APIs.

Repository layout:
```
cosmic-triage/
  src/cosmic_triage/{contracts,ingest,belief,value,schedule,replay,investigator,metrics,api}/
  src/cosmic_triage/investigator/{tools,orchestrator,ledger,validators,extractors,routers}/
  configs/{objectives,facilities,policies,investigator}/
  data/cache/   runs/   docs/   console/ (React)
  tests/{unit,leakage,fixtures}
```

---

## 10. Milestones — dependency-ordered, with completion criteria and learning checkpoints

### 10.1 Two tracks, one rule
- **Demo track (exploratory):** gets an end-to-end Investigator running on real candidates as early as possible, including exploratory Jev integration. Runs with `mode: exploratory`, writes to `runs/exploratory/`, and **never contributes a number to a benchmark table.**
- **Bench track (rigor):** forward pool, temporal splits, baselines, Tier A/B/C metrics with CIs. A component *graduates* from demo to bench only through M4's harness.
This separation is what lets Jev and the Investigator appear in week 1 without contaminating the eventual benchmarks: exploratory runs inform design and the console; benchmark runs are the only source of claims.

Working target: **M0–M4 in roughly two weeks.** The completion criteria below are not negotiable to hit that target; if they slip, the date slips.

### 10.2 Dependency graph
```
M0 access + scaffold + contracts
 └─► M1 candidate spine (leakage-safe data, console v0)
      ├─► M2 Investigator v1 + exploratory end-to-end demo (Jev gate/verifier, flagged)
      └─► M3 decision substrate (belief v0, rewards, scheduler, baselines, replay)
            └─(needs M2 claims + M3 effects)─► M4 Benchmark v1 ── mandatory Fable review
                                                 ├─► M5 cascades & context (Tier C)
                                                 ├─► M6 memory & reliability
                                                 ├─► M7 multimodal (needs M0 #8)
                                                 └─► M8+ depth (sncosmo channel, EVSI, O3, Rubin, live)
```
M2 and M3 are independent after M1 and may be interleaved; M4 requires both.

### 10.3 Milestones

**M0 — Access, scaffold, contracts.** *Depends on:* nothing.
Deliverables: repository scaffold (§9 layout); `contracts` package with every type in §3/§4.3; `scripts/m0_killtests.py` executing all §11 kill-tests and writing `runs/m0/killtests.md`; recorded HTTP fixtures for every external API touched; `.env.example`; pre-commit (ruff).
Completion criteria: all 12 kill-tests have a recorded verdict and, for failures, the fallback chosen (fallbacks for #1–#5 require a Fable decision, §14); every contract round-trips JSON via `model_validate(model_dump())`; `uv run pytest` green with **no network** (`COSMIC_OFFLINE=1`).
Learning checkpoint 0 — *decisions:* why typed contracts precede any logic; why fixtures are recorded. *Concepts:* MJD, AB magnitudes, alert vs object, detection vs upper limit. *Explain independently:* what each external source provides and cannot (especially why ALeRCE `lc_classifier` probabilities are unusable in replay).

**M1 — Candidate spine (leakage-safe data + console v0).** *Depends on:* M0.
Deliverables: `ingest` clients (ALeRCE, Fink, BTS, Lasair) behind one disk `Cache` with offline mode; `replay.Clock` + `Snapshot(t)` with denylist; `ForwardPool` with the time-honest pre-filter (§6.4); BTS catalog snapshot with labels {class, unknown, contaminant}; `tests/leakage/` adversarial fixtures; console v0: candidate table, light curve with non-detections and a time cursor, and **Night Theater S0** (§8.2: static alt-az dome with precomputed `NightFrame`s).
Completion criteria: `Snapshot(t)` for 5 consecutive nights builds from cache in < 60 s; ≥ 20 leakage fixtures pass — including a detection at t + 0.01 d, a Fink row with `jd > t`, a BTS `type` field, and an `ndethist` taken from the final history — each must be absent or recomputed; pool-size and bright-candidate counts per night recorded in `runs/m1/pool_stats.md` with the **budget-binding check** (§6.3); console renders any pool candidate at any t.
Learning checkpoint 1 — *decisions:* forward pool vs retrospective cohort; the denylist as a type-level boundary; why "never-saved & filter-passing & bright ⇒ contaminant" is defensible (BTS II audit). *Concepts:* selection bias and completeness; survey cadence; what a non-detection constrains. *Explain:* three ways future information could leak into a replay and how each is blocked here.

**M2 — Investigator v1 + exploratory end-to-end demo.** *Depends on:* M1. *(The early demo target.)*
Deliverables: `ToolRegistry` with ≥ 6 tools — report lookup (TNS bot or Lasair-TNS fallback), Sherlock, SIMBAD cone, alert history, cutouts, offset/absolute-magnitude calculator — each with typed I/O, an **as-of filter at the tool layer**, caching, typed errors, retries; `EvidenceLedger`; `Validator` chain (schema, provenance-exists, `source_date ≤ t`, geometry recomputed, type-specific); Claude (Sonnet) `Extractor` → `ClaimDraft`s via structured output; code-owned `Orchestrator` loop with budgets and stop conditions; **exploratory Jev** behind config flags — gate `Noul` and support-verifier `Noul`, called and logged (latency, tokens, $, answer) but not yet gating benchmarks; `Trace` JSONL; console: investigation trace view and ledger browser with the leakage badge; `scripts/demo_investigate.py OID MJD`.
Completion criteria: on 20 candidates at chosen t (10 BTS-classified, 10 contaminant/unknown): 100% of runs terminate within budget; **0 accepted claims with `source_date > t`** (a test asserts this over all traces); ≥ 80% of runs end with ≥ 1 validated claim or an explicit `no_context_found`; every run's trace renders in the console; Jev calls logged for all 20; a hand review of all 20 dossiers filed in `runs/reports/M2.md` with error categories; `demo_investigate.py` runs end-to-end on a clean checkout with cache in < 2 min.
Learning checkpoint 2 — *decisions:* why orchestration is code-owned with swappable slots; why claims are typed and validated before they can matter; why Jev is wired as gate/verifier and not as a classifier. *Concepts:* tool contracts, structured outputs, provenance, as-of retrieval, idempotency, budgets/stop conditions, observability spans. *Explain:* the full path of one claim from tool output to ledger to (future) reward effect, and every place it could be rejected.

**M3 — Decision substrate (beliefs, rewards, scheduler, baselines, replay).** *Depends on:* M1 (may interleave with M2).
Deliverables: `belief` channels (Fink per-alert, stamp class, history features) → per-channel temperature scaling → pooled multinomial LR, fit on a training window strictly before the evaluation window; `RewardTable`s O1/O4 in `configs/objectives/*.yaml` with `version` and a frozen hash; `ClaimEffects` map (§4.1); astroplan windows; exposure model; CP-SAT `Scheduler` + independent `FeasibilityChecker`; policies: random, brightest-first, broker-greedy × brightness × visibility, AAS2RTO-like, BTS-mimic, L0-ours, oracle; replay loop with ZTF-record weather + seeded downtime; console: Gantt with constraint toggles and re-solve, belief-by-channel, policy compare, and **Night Theater S1** (night player driven by `Schedule`/`Outcome` artifacts, ghost styling + L-badges for simulated activity).
Completion criteria: checker reports 0 violations on 30 random nights for all policies; a full-night replay of all policies < 2 min; calibration plot (ECE, log-loss per epoch) produced for the training window and the single-best-channel gate (§6.1) enforced; reward tables frozen (hash recorded) **before** any policy comparison runs; two runs with the same seed produce identical output hashes.
Learning checkpoint 3 — *decisions:* channel partition and learned pooling instead of naive products; direct reward vs EVSI vs EIG (work `REVIEW-01-addendum.md` §1.4 by hand); why BTS-mimic is "truth-correlated"; why the budget must bind. *Concepts:* Bayes with nuisance parameters, calibration (ECE/Brier), temperature scaling, interval scheduling in CP-SAT, airmass/twilight/Moon constraints. *Explain:* why a greedy entropy planner would waste observations, with numbers.

**M4 — Benchmark v1 (rigor gate; Jev graduates).** *Depends on:* M2 and M3. **Ends with a mandatory Fable review.**
Deliverables: evaluation window ≥ 60 nights (target 120) with rolling-origin splits; Tier A on ≥ 200 candidates; Tier B with/without Investigator stratified easy/ambiguous/contaminant; wasted-spectrum metric; first Tier-C slice (Jev gate and verifier vs their baselines); simulation-ladder labels on every number; `runs/reports/M4.md` with tables and bootstrap CIs; console: agent-vs-no-agent diff and **Night Theater S2** (Investigator events on the timeline, A/B domes).
Completion criteria: leakage rate exactly 0 over all benchmark traces; §7.4 pre-registered verdicts filled in with CIs; every table row carries an L-level; full benchmark reproducible from cache with a fixed seed (identical hashes on re-run); the report lists every decision Opus made unilaterally (§14) for review.
Learning checkpoint 4 — *decisions:* what the Investigator's decision impact is and is not; which Jev roles survived and why; what the ladder labels protect against. *Concepts:* rolling-origin evaluation, bootstrap CIs over nights, stratified analysis, regret vs oracle, pre-registration. *Explain:* the headline result to a skeptical engineer, including its three biggest caveats.

**M5 — Cascades & context engineering (Tier C).** *Depends on:* M4. Deliverables: Haiku→Sonnet→Opus extractor cascade; Jev router and relevance scorer vs baselines; context-budget sweep (2k/8k/32k); option-order flip test; cost–quality frontier; console cascade dial; **Night Theater S3** polish begins here and continues alongside M6–M7. Completion: frontier with ≥ 6 configurations and CIs; flip rates reported; the best configuration adopted by config change only.
Learning checkpoint 5 — routing, cascades, confidence-gated escalation, context packing, state design for a bounded model.

**M6 — Memory & reliability.** *Depends on:* M4. Deliverables: cross-night ledger persistence, compaction, staleness policy; chaos-injection harness (per-tool error rates 0/10/30%); idempotent re-runs. Completion: memory on/off table (cost, accuracy, staleness errors); degradation curves; re-run determinism under injected failures.
Learning checkpoint 6 — state/memory design, failure taxonomies, circuit breakers, graceful degradation.

**M7 — Multimodal.** *Depends on:* M4, M0 #8. Deliverables: cutout triplets → Jev-1.14 / Claude vision as a channel; `btsbot` and ALeRCE stamp baselines. Completion: AUROC/cost table; pooling-weight verdict.
Learning checkpoint 7 — when multimodal models add information over a trained CNN, and how to prove it.

**M8+ — Depth.** sncosmo likelihood channel; EVSI for *wait*/photometry; second facility; O3 submodular reward; Rubin stream; live nightly plan; write-up.

### 10.4 First vertical slice (end of M2)
`scripts/demo_investigate.py <OID> <MJD>` on a BTS-classified 2025 SN: `Snapshot(t)` → stub belief from the Fink score → `Orchestrator.run` → tools → validated claims → printed reward delta via `ClaimEffects` → `Trace` JSONL → console renders light curve, trace, and ledger. It touches every layer; nothing it prints is a benchmark claim.

---

## 11. Risks and kill-tests (M0)
| # | Assumption | If false | Test |
|---|---|---|---|
| 1 | TNS report/classification dates obtainable (individual bot) | fall back to Lasair/Fink TNS crossmatch tables (dates may be partial); Tier-A truth narrower | register; one query |
| 2 | Fink `/objects` POST returns per-alert `d:*` incl. `d:tns`, with upper limits | lose replay-safe photometry channel and alert-time TNS flag; use ALeRCE + stamp prior only | one POST |
| 3 | Forward-pool volume per night is manageable (≤ ~500 after pre-filter) | tighten pre-filter; cache more aggressively | 5 nights of `/objects?firstmjd` |
| 4 | Budget binds (median bright SN-like candidates / slots ≥ 2) | shrink budget | count over candidate window |
| 5 | BTS CSV without filters includes unclassified saved candidates | redefine unknown bucket | one download |
| 6 | Lasair token + Sherlock available; SIMBAD/NED astroquery rate limits tolerable with caching | drop/replace tools | smoke tests |
| 7 | Jev and Claude keys; Jev call ≈ 200 ms with ~500-token state | M4 slips; architecture unaffected | one call each |
| 8 | `btsbot` installs and runs on ALeRCE stamps | multimodal baseline becomes ALeRCE stamp only | inference on 10 alerts |
| 9 | CP-SAT solves 60 targets × 12 h in < 5 s | greedy by expected reward | toy model |
| 10 | Corpus ingestion (AstroNotes/ATels/GCN) feasible with dates | restrict to TNS + catalogs for M2 | crawl 1 month |
| 11 | Investigator decision impact may be small on easy candidates | report null honestly; stratify; the engineering/eval deliverables stand | M3 design |
| 12 | Jev first-option bias / literal reading | randomize order, measure flips | M4 |

What is real: photometry, non-detections, timestamps, coordinates, catalog matches, dated reports, BTS classes, geometry, exposure scaling. Inferred: beliefs, phase, contaminant labels. Simulated and labeled: spectrum reveals (L2), downtime (L1), synthetic photometry (L3).

---

## 12. Record of decisions (what changed and why)
- **v0 → Addendum 01:** EVOI corrected to direct reward + EVSI (EIG diagnostic only); evidence channels partitioned and pooled with learned weights to stop double counting (Fink × templates, Jev × everything); retrospective cohort replaced by a forward pool with bright-regime scoring and strict temporal splits; simulation ladder; overpacked weekend replaced by staged milestones.
- **Addendum 01 → v1 (Review 02):** project re-centered on the Investigator as the AI-engineering core after the goal clarification; template-likelihood engine demoted to a tool (M7 channel); broker scores + calibration as M1 belief; Jev given four bounded roles with baselines; prior-art read in full and reproduced as baselines; BTS completeness logic tightened to "never-saved & filter-passing & bright ⇒ contaminant"; weather proxy limited to Palomar nights + seeded downtime; label volume/drift assessed; console gains investigation trace, ledger browser, agent diff, cascade dial; milestones M0–M7 with no Monday deadline.
- **v1 handoff update (2026-10-18):** milestones replaced by dependency-ordered M0–M8 with measurable completion criteria and learning checkpoints; demo/bench track separation so the Investigator and exploratory Jev run in week 1 without contaminating benchmarks; §13 implementation handoff and §14 return-to-Fable triggers added. No architectural change.
- **Night Theater added (2026-10-18):** §8.2 — planetarium-style simulation mode as a first-class demo requirement, phased S0–S3 across M1/M3/M4/M5+, bound by the rule that it is a player of replay artifacts with real-vs-simulated always visible.
- **Road not taken:** an SEC-EDGAR filings investigator scored highest on evaluation rigor among alternatives but lower on domain engagement, multimodal fit, and objective downstream value; documented in `REVIEW-02.md` §F.3.

---

## 13. Implementation handoff (for the implementing model)

### 13.1 Workflow
Two-model workflow: **Fable** owns this document, architectural decisions, and milestone reviews; **Opus** implements, tests, debugs, and builds the console. Opus works milestone by milestone, starting a fresh session per milestone with this file as context, and ends each milestone with `runs/reports/M<N>.md` (results, decisions made unilaterally, open questions). Reports are not architecture documents; this file remains the only source of truth and is edited only by Fable.

### 13.2 Conventions (binding)
- Python 3.12, `uv`, `src/` layout, pydantic v2 contracts, ruff; type hints everywhere; `mypy --strict` on `contracts` and `investigator`.
- **No network in tests.** Every external call goes through `ingest.Cache`; tests run with `COSMIC_OFFLINE=1` against recorded fixtures under `tests/fixtures/`. A test that needs the network is a bug.
- **Snapshot-only data access** outside `replay`: no module other than `replay` may import `BTSCatalog` labels or read raw cache tables; `Snapshot(t)` is the only input to `belief`, `value`, `schedule`, `investigator`. Enforced by an import-linter rule and a test.
- **Determinism:** every run takes `seed` and `config_hash`; identical inputs → identical output hash; model calls are recorded to fixtures for replayable tests (`anthropic`/`typesafe` responses cached by request hash in offline mode).
- **Configs are versioned YAML** with a `version` field and a content hash logged into every run. Reward tables, pre-filter, denylist, and metric definitions are config, not code constants.
- **Traces:** one JSONL file per run under `runs/{exploratory|bench}/<date>/<run_id>.jsonl`, with spans (`tool`, `model`, `validator`, `solver`), resolved model ids, tokens, USD.
- **Units:** MJD for time, AB magnitudes, arcseconds for separations, degrees for sky coordinates; documented in `contracts/units.py`.
- Secrets only via `.env` (`ANTHROPIC_API_KEY`, `TYPESAFE_API_KEY` or `OPENROUTER_API_KEY`, `LASAIR_TOKEN`, `TNS_BOT_ID/NAME/API_KEY`); never in fixtures (scrub headers when recording).
- Console: Vite + React + TypeScript; types generated from pydantic (`pydantic2ts` or `datamodel-codegen`); Plotly for plots; no backend logic in the console.

### 13.3 Initial modules and interfaces (M0–M3)
```python
# contracts/ — all pydantic; see §3, §4.3. Additive optional fields are fine; semantic changes go to Fable (§14).
PhotometryPoint, CandidateContext, CandidateState, Snapshot, Belief, Objective, RewardTable,
Action, Schedule, Outcome, Evidence, Claim, ClaimDraft, ValidationReport, EvidenceLedger,
Span, Trace, DecisionTrace, Label(Literal["class","unknown","contaminant"]), RunConfig

# ingest/
class Cache:            get(key) / put(key, payload) ; offline: bool ; key = (client, method, canonical_params)
class AlerceClient:     objects(firstmjd: tuple, **filters) -> list[dict]; lightcurve(oid) -> dict; probabilities(oid) -> list[dict]; stamp(oid, candid, kind) -> bytes
class FinkClient:       object_rows(oid, with_upperlim=True) -> list[dict]
class LasairClient:     sherlock(ra, dec) -> dict; object(oid) -> dict; tns_crossmatch(oid) -> list[dict]
class TNSClient:        search(ra, dec, radius_arcsec) -> list[dict]; get_object(name) -> dict   # or LasairTNSFallback
class BTSCatalog:       load(snapshot_date) -> DataFrame; label(oid, scored_regime: bool) -> Label

# replay/
class Clock:            snapshot(t_mjd, pool: ForwardPool) -> Snapshot      # applies denylist; recomputes ndethist from ≤ t
class ForwardPool:      candidates(t_mjd) -> list[oid]                      # §6.4 pre-filter, time-honest
class Replay:           run(policy, nights, config) -> ReplayResult          # outcomes, weather from ZTF record + seeded downtime
class Oracle:           reward(oid, action, t) -> float                      # truth-reading; replay-only

# investigator/
class Tool(Protocol):   name: str; Input: type[BaseModel]; Output: type[BaseModel]; as_of_aware: bool
                        def run(self, inp: BaseModel, t_mjd: float) -> BaseModel      # raises ToolError subclasses
class ToolRegistry:     register(tool); get(name); describe() -> list[ToolSpec]   # ToolSpec feeds the planner prompt / Jev Choice criteria
class Gate(Protocol):   decide(belief, objective, ledger) -> GateDecision         # impls: EntropyGate, AlwaysGate, JevNoulGate
class Planner(Protocol):next_tool(ledger, budget, tools) -> ToolCall | Stop       # impls: FixedOrderPlanner, LLMPlanner, JevChoicePlanner
class Extractor(Protocol): draft(context_pack) -> list[ClaimDraft]              # impls: ClaudeStructuredExtractor (Sonnet), Cascade (Haiku→Sonnet)
class Validator:        validate(draft, ledger, t_mjd) -> ValidationReport       # chain: schema, provenance, date<=t, geometry, type-specific, support
class SupportVerifier(Protocol): score(claim, evidence) -> float                 # impls: JevNoulVerifier, ClaudeJudge, DeterministicOnly
class Orchestrator:     run(oid, snapshot, objective, belief, config) -> (EvidenceLedger, Trace)
class ContextPacker:    pack(ledger, budget_tokens, scorer) -> ContextPack       # scorer impls: Recency, BM25, JevScore

# belief/
class Channel(Protocol):logp(candidate: CandidateState) -> dict[ClassK, float]  # FinkScoreChannel, StampChannel, HistoryChannel, (M8) TemplateChannel
class Calibrator:       fit(logps, labels) ; apply(logps)                        # temperature scaling per channel
class Pool:             fit(channel_logps, labels) ; predict(channel_logps) -> Belief
# value/
class RewardTable:      load(path) -> RewardTable ; expected_reward(belief, phase_bin, action) -> float
class ClaimEffects:     apply(claims, belief, reward_ctx) -> (Belief, RewardCtx, EffectLog)
class EVSI:             one_step(action, belief, tomorrow_alloc) -> float        # M8; stub returns 0 before then
# schedule/
class Visibility:       windows(targets, night, facility) -> dict[oid, list[Interval]]   # astroplan
class ExposureModel:    duration_s(mag, instrument) -> float
class Scheduler:        solve(actions, windows, facility, budget) -> Schedule    # OR-Tools CP-SAT
class FeasibilityChecker: check(schedule, facility, night) -> CheckReport        # independent of the solver
# metrics/
tier_a(traces, truth) ; tier_b(replay_results) ; tier_c(configs) ; bootstrap_ci(values, n=2000, seed)
ladder_level(metric_name) -> Literal["L0","L1","L2","L3"]
# api/theater (Night Theater, §8.2) — player data only, no logic
class NightFrame(BaseModel):   # one per 5-min step; computed with astropy in Python
    t_mjd: float; sun_alt: float; moon: {alt, az, phase}; twilight: Literal["day","civil","nautical","astro","night"]
    candidates: list[{oid, alt, az, belief_top, expected_reward, is_real_detection_now: bool}]
    facility: {pointing_oid | None, state: Literal["idle","slewing","exposing","down"], sim_level: "L1"}
    events: list[{kind: "detection"|"report"|"gate"|"tool"|"claim"|"schedule"|"outcome", ref_id, sim_level}]
GET /theater/nights ; GET /theater/{run_id}/{night}/frames ; GET /theater/{run_id}/{night}/events
```

### 13.4 Dependencies
Runtime: `pydantic>=2`, `httpx`, `duckdb`, `pyarrow`, `pandas`, `numpy`, `scipy`, `scikit-learn`, `astropy`, `astroplan`, `ortools`, `anthropic`, `typesafe-sdk` (or OpenRouter via `httpx`), `rank-bm25`, `fastapi`, `uvicorn`, `sse-starlette`, `pyyaml`, `python-dotenv`. Later: `sncosmo` (M8), `btsbot` + torch (M7), `dustmaps` (M8). Dev: `pytest`, `pytest-recording` (vcrpy), `ruff`, `mypy`, `import-linter`, `hypothesis`. Console: `vite`, `react`, `typescript`, `plotly.js`, `d3`.

### 13.5 Tests and acceptance
- `tests/unit/` per module; `tests/leakage/` adversarial fixtures (§10.3 M1) and an all-traces assertion that no accepted claim cites `source_date > t`; `tests/contracts/` round-trip and schema-snapshot tests (a schema change fails CI until the snapshot is intentionally updated); `tests/schedule/` property tests (hypothesis) that the checker rejects every mutated schedule; `tests/investigator/` corrupted-claim fixtures (wrong coordinates, future dates, unsupported excerpts) that must be rejected; determinism test (same seed → same hash) for replay and orchestrator; golden traces for `demo_investigate.py`.
- Acceptance per milestone = the completion criteria in §10.3, verified by a script `scripts/accept_M<N>.py` that prints pass/fail per criterion and is committed with the milestone report.

### 13.6 Known risks for the implementer
Weakening a test to make it pass (forbidden; see §14); hidden network calls in tests; future-data leakage through pandas joins on final tables (use `Snapshot` only); ALeRCE `/objects` filter quirk (verify with per-oid `/probabilities`); Fink POST shape differing from docs; SIMBAD/NED rate limits (cache aggressively, batch cone searches); TNS bot availability; Jev first-option bias (randomize `Choice` order; log order); console scope creep (time-box; results before pixels); model-call nondeterminism (record responses; temperature 0 where supported; log resolved ids).

### 13.7 First vertical slice
§10.4: `scripts/demo_investigate.py <OID> <MJD>` end-to-end on a BTS-classified 2025 SN, with the trace visible in the console. Pick the OID from the BTS CSV (an SN Ia with a Sherlock host match and a TNS classification report) during M1.

---

## 14. When to stop and return to Fable
Opus must stop, write the question into `runs/reports/M<N>.md` under **"Needs architecture decision"**, and not proceed on that item when any of the following would otherwise happen:
1. **Contract semantics change** — any non-additive change to a type in §3/§4.3 or to `Snapshot`'s denylist. (Adding optional fields is fine.)
2. **Evidence path change** — adding or removing a belief channel; changing the pooling method; letting *any* LLM/Jev output influence a probability or reward other than via a validated `Claim` → `ClaimEffects` or a learned pool weight.
3. **Reward or metric change** — editing reward tables after M4 begins; changing a metric definition, an L-level assignment, the scoring regime (peak ≤ 18.5), the pre-filter, the temporal-split rule, or the label rules in §6.4.
4. **Jev scope change** — a Jev role beyond the five in §5; using Jev for arithmetic, counting, dates, or numeric interpolation; feeding it raw light-curve numbers.
5. **Solver or objective change** — replacing CP-SAT, changing the objective's functional form, or relaxing a hard constraint to make schedules feasible.
6. **Agentic scope change** — any multi-agent orchestration, agent-executed code, free-running loops without budgets, or tools that write to external systems.
7. **Kill-test fallbacks** for §11 #1–#5 (TNS access, Fink per-alert rows, pool volume, budget binding, BTS unclassified rows).
8. **A test must be weakened, skipped, or deleted** to pass; or a leakage assertion fails.
9. **Spend** exceeds the monthly ceiling set by the owner, or a benchmark would need more than 2× the projected model cost.
10. **Prior-art substitution** — discovering an existing component that would replace a module (e.g., using `aas2rto` clients wholesale).
11. **Ambiguity touching §1.4** (the governing rule). For other ambiguities: choose the simplest option, record it under "Decisions made" in the milestone report, and continue.
Milestone M4 ends with a mandatory Fable review regardless.

---

## 15. Sources
**Jev:** [docs.typesafe.ai](https://docs.typesafe.ai/introduction) · [llms.txt index](https://docs.typesafe.ai/llms.txt) · [API](https://docs.typesafe.ai/api.md) · [confidence](https://docs.typesafe.ai/confidence.md) · [state](https://docs.typesafe.ai/concepts/state.md) · [jev-1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md) · [quickstart](https://docs.typesafe.ai/introduction/quickstart.md) · [OpenRouter guide](https://openrouter.ai/docs/guides/community/jev) · [model page](https://openrouter.ai/typesafe/jev-1.14) · [Banking77 benchmark](https://openrouter.ai/blog/insights/jev-vs-claude-opus-5-classification/) · [jev-bench](https://github.com/stern9/jev-bench)
**Data:** [ALeRCE docs](https://alerce.readthedocs.io/en/latest/) · [ALeRCE API](https://api.alerce.online/ztf/v1/classifiers) · [BTS Explorer](https://sites.astro.caltech.edu/ztf/bts/explorer.php) · [Fink ZTF docs](https://doc.ztf.fink-broker.org/services/search/getting_started/) · [fink-object-api](https://github.com/astrolabsoftware/fink-object-api) · [Lasair API](https://lasair.readthedocs.io/en/main/core_functions/rest-api.html) · [ZTF alert archive](https://ztf.uw.edu/alerts/public/) · [TNS getting started](https://www.wis-tns.org/content/tns-getting-started) · [TNS API manual](https://www.wis-tns.org/sites/default/files/api/TNS_APIs_manual.pdf) · [Rubin alerts & brokers](https://rubinobservatory.org/for-scientists/data-products/alerts-and-brokers) · [ALeRCE labeled set](https://zenodo.org/records/4279623) · [ELAsTiCC](https://portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC/)
**Prior art (read in full):** [REFITT, Sravan+2020](https://arxiv.org/abs/2003.08943) · [refitt code](https://github.com/refitt/refitt) · [BTSbot, Rehemtulla+2024](https://arxiv.org/abs/2401.15167) · [btsbot code](https://github.com/nabeelre/BTSbot) · [AAS2RTO, 2025](https://arxiv.org/abs/2501.06968) · [aas2rto code](https://github.com/aidansedgewick/aas2rto) · [RESSPECT, Kennamer+2020](https://arxiv.org/abs/2010.05941) · [RESSPECT code](https://github.com/COINtoolbox/RESSPECT) · [BTS II, Perley+2020](https://arxiv.org/abs/2009.01242) · [Fink real-time AL](https://arxiv.org/abs/2502.19555) · [BTSbot-nearby](https://arxiv.org/abs/2501.18686)
**LLMs in astronomy:** [RADAR](https://arxiv.org/abs/2609.18233) · [AstroAlertBench](https://arxiv.org/abs/2605.05573) · [ALeRCE text-to-SQL](https://arxiv.org/html/2606.18108v1) · [Autonomous research agents & the verification gap](https://arxiv.org/abs/2608.05179)
**Scheduling, instruments, libraries:** [LUMOS](https://arxiv.org/abs/2601.08912) · [LCO ILP scheduler](https://www.researchgate.net/publication/274094520_An_Integer_Linear_Programming_Solution_to_the_Telescope_Network_Scheduling_Problem) · [ZTF scheduler](https://arxiv.org/pdf/1905.02209) · [SED Machine](https://arxiv.org/pdf/1710.02917) · [Spectral classifier accuracy on 4,646 SEDM spectra](https://arxiv.org/pdf/2410.10963) · [astroplan scheduling](https://astroplan.readthedocs.io/en/stable/tutorials/scheduling.html) · [sncosmo sources](https://sncosmo.readthedocs.io/en/stable/source-list.html) · [Vincenzi+2019 templates](https://arxiv.org/html/1908.05228) · [SkyPortal API](https://skyportal.io/docs/api.html)
