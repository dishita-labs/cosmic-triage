# Cosmic Triage — Review 02: Is this the right project, and what should its AI core be?

*2026-10-17. Responds to review items A–F plus the clarified goal: become an excellent engineer of LLM-powered and agentic systems; astronomy is the chosen unfamiliar domain, not the objective. No code has been written.*

---

## F. Independent judgment on project choice (read first)

### F.1 The honest diagnosis of the current design
Through `ARCHITECTURE.md` v0 and `REVIEW-01-addendum.md`, Cosmic Triage is **roughly 80% statistical modeling, numerical optimization, and data engineering, and 20% LLM/agent engineering** — and the 20% is thin:

| Component in v0/Addendum-01 | What it teaches | LLM/agent content |
|---|---|---|
| Ingest, caching, leakage-safe snapshots | data engineering, temporal correctness | none |
| sncosmo template likelihoods, nuisance marginalization | Bayesian inference, physics | none |
| Calibration + learned pooling | ML evaluation, probabilistic ML | none (Jev as one input) |
| Reward tables, EVSI | decision theory | none |
| CP-SAT scheduling | combinatorial optimization | none |
| Replay harness + metrics | experimental design | none |
| Scanner (Jev / Claude / GBM) | LLM-as-classifier, calibration, option-order bias | **a benchmark, not a system**: one call, no tools, no state |
| Confidence-gated escalation | cascades | small |
| Objective parsing, explanation + Jev verification | structured outputs, verification | small, peripheral |

That is a superb project for learning Bayesian decision-making and optimization. Measured against the clarified goals — orchestration, tool use, multi-step reasoning, context engineering, retrieval, memory/state, routing/cascades, reliability/grounding/failure recovery, multimodal, agent evaluation, LLM+deterministic integration — **it is the wrong shape.** You would spend most of your weeks on numpy and OR-Tools and would learn LLM engineering mostly through a classification ablation. I was wrong to let the first two documents drift there; the brief asked for a "hybrid AI architecture," and I optimized for scientific defensibility over your actual learning objective.

### F.2 Is there an *authentic* agentic problem in this domain?
Yes — and it has been hiding in plain sight in the prior art. BTS II §2.2 ("Candidate Characterization") describes what human scanners do *after* the numeric filter and *before* committing a spectrograph: visually inspect the light curve, **cross-match to catalogs**, check whether the transient is **coincident with a known AGN or a WISE source with AGN-like colors**, whether a **star-like counterpart** exists, whether **previous flares** are visible in history, whether it was **already reported or classified on TNS by another group** ("we avoid duplicating effort"), and whether a **host redshift** is known. The REFITT paper explicitly lists "contextual information (Milky Way extinction, galaxy association)" from brokers as the most valuable missing input. This step is:

- **Genuinely multi-source and heterogeneous:** structured catalogs (SIMBAD, NED, Gaia, WISE, Pan-STARRS), semi-structured reports (TNS discovery/classification reports, AstroNotes, ATels, GCN circulars), alert histories across brokers, image cutouts, and literature.
- **Genuinely tool-using:** cone searches, host-association logic, offset and absolute-magnitude arithmetic, template fits, color evolution, dust maps — each a validated numeric tool the agent must *choose to call and read correctly*, not emulate.
- **Genuinely stateful across time:** a candidate is re-examined on successive nights; the dossier should accumulate, compact, and go stale.
- **Genuinely time-stamped**, which is rare and precious for agent evaluation: TNS reports, AstroNotes, ATels, GCNs, and alert packets all carry dates, so an "as-of t" retrieval layer can be built and **temporal leakage can be tested mechanically** — every claim's provenance must be dated ≤ t.
- **Genuinely consequential downstream in a deterministic way:** "already classified by another group at time t" makes a spectrum worthless (reward → 0); a catalog host redshift converts apparent to absolute magnitude and eliminates classes; a known AGN or dwarf-nova history sets a contaminant prior. These are hard, codeable effects on a Bayesian decision engine — which gives agent work an **objective value metric** that most agent projects completely lack.

That problem — call it the **Investigator** — exercises every item on your list:

| Your learning goal | Where the Investigator exercises it authentically |
|---|---|
| LLM architecture, tool calling, orchestration, multi-step reasoning | A code-owned orchestration loop over a typed tool registry (8–12 scientific/retrieval tools), with budgets, parallel vs sequential tool calls, planning vs reactive variants |
| Context engineering, retrieval, memory, state | As-of retrieval over dated corpora; context packing under token budgets; an append-only **evidence ledger** per candidate with provenance; cross-night compaction; staleness handling |
| Specialized models (Jev), routing, cascades | Jev as gate ("worth investigating?"), as tool-router ("which tool next?"), as claim-support verifier, as relevance scorer for context packing; Haiku→Sonnet→Opus cascade with measured cost–quality frontiers |
| Reliability, grounding, validation, failure recovery | Typed claims that must pass deterministic validators (coordinates within radius, date ≤ t, numeric consistency, source actually contains the quoted record) before they can touch a belief; failure-injection (timeouts, 429s, malformed responses, contradictory sources) with measured degradation |
| Multimodal where it fits | Cutout triplets → Jev-1.14 / Claude vision for real/bogus, nuclear-vs-offset, host morphology, against a *serious* public baseline (BTSbot weights on HuggingFace, `pip install btsbot`) |
| Rigorous evaluation of AI systems | Component metrics (extraction accuracy vs ground truth, grounding rate, leakage rate = 0 by construction check), decision-impact metrics (calibration, selection yield with vs without), architecture ablations (cascade tiers, context budgets, memory on/off, tool-set), cost/latency |
| LLM + deterministic software + numerical models + tools | The thesis of the design: **LLM proposes, tools compute, validators gate, the Bayesian engine integrates, the solver decides** |

### F.3 Alternatives I seriously considered (other unfamiliar industries included)
Scored 1–5 on your criteria. "Objective downstream value" = whether there is a non-LLM way to tell if the agent's work actually mattered.

| Candidate project | LLM/agent depth | Unfamiliar & engaging | Real data, free | Ground truth / eval | Objective downstream value | Multimodal fit | Demo | Notes |
|---|---|---|---|---|---|---|---|---|
| **Cosmic Triage re-centered on the Investigator** | 5 | 5 | 5 | 4 | **5** (Bayesian engine + replay) | 4 | 5 | Risk: decision-impact may be small for easy candidates; learning survives a null result because the engineering and evals are the product |
| SEC EDGAR filings investigator (XBRL facts as machine ground truth; as-of retrieval over 8-K/10-K; routing/cascades) | 5 | 2 | 5 | **5** | 3 (financial models are shallow here) | 1 | 3 | Strongest evaluation rigor of any option; weakest on fun and "unfamiliar domain"; crowded space |
| Clinical-trial dossier agent (ClinicalTrials.gov + PubMed + FDA labels; predict registry outcome fields) | 4 | 4 | 5 | 4 | 2 | 1 | 3 | Rich text, dated updates; no deterministic engine to integrate with; regulatory text is a slog |
| CI-failure / incident triage agent over public OSS repos (logs, issues; truth = the actual fix commit) | **5** | 1 | 5 | 4 | 4 | 1 | 4 | Purest agent-engineering; least unfamiliar; SWE-agent territory is crowded and well-trodden |
| Patent prosecution outcome investigator (USPTO PatentsView + office actions) | 4 | 3 | 4 | 4 | 2 | 1 | 2 | Decent, but mostly document QA |
| Multi-messenger GCN-circular follow-up agent (RADAR-like) | 4 | 5 | 5 | 3 | 4 | 2 | 4 | Essentially a variant of the Investigator restricted to GW/GRB text; smaller event count; strong prior art (RADAR, 2026) |

The re-centered Cosmic Triage wins on the dimension that matters most for *rigor* in agent engineering and that almost every alternative lacks: a **deterministic, replayable consumer** of the agent's outputs that turns "the agent found X" into "selection yield changed by Y with a confidence interval." EDGAR is the one alternative I would pick if you told me the astronomy pull were weak — it isn't.

### F.4 Recommendation
**Stay with Cosmic Triage. Re-center it.** The central AI-engineering challenge becomes:

> **A grounded, budgeted, tool-using scientific Investigator whose typed, provenance-backed claims are validated before they enter a Bayesian follow-up planner — evaluated by leakage-safe historical replay against real outcomes, with measured cost–quality tradeoffs across model cascades, context budgets, memory strategies, and tool sets.**

The scientific engine (beliefs, rewards, scheduler, replay) is **kept but minimized** to what makes the Investigator's value measurable and the demo credible: broker classifier scores + calibration as the initial belief source (not a grid-marginalized sncosmo engine), a small CP-SAT scheduler, and the replay harness. Physics-template fitting becomes a **tool the agent can call** and a later upgrade, not the critical path. Rebalance target: **~65% LLM/agent engineering, ~35% scientific substrate** — with the substrate front-loaded in week 1 because without it there is no objective metric.

Plainly: the risk is that for most bright, easy candidates the deterministic crossmatches already supply the key facts and the agent's *decision* impact is small. That is a legitimate finding, and the project remains excellent for your goals because the deliverables are the orchestration, grounding, state, routing, evaluation harness, and the measured frontier of where an investigator helps. Design choices below maximize the chance of a real, honest signal (ambiguous and contaminant candidates; already-classified detection; reconciliation of conflicting sources).

---

## A. The Investigator — capability by capability

Rule that governs everything: **hypotheses are generated; probabilities are computed.** An LLM may propose, retrieve, extract, and explain. It may never emit a probability that enters a belief. The only path from Investigator to belief is a **typed claim** that passed a deterministic validator and maps to a pre-registered, code-owned effect.

### A.1 Capabilities

| # | Capability | Concrete problem it solves | Why an LLM (and not code) | Boundary | Interaction with the engine | How we measure added value |
|---|---|---|---|---|---|---|
| 1 | **Prior-report & classification lookup** (TNS reports, AstroNotes, ATels, GCNs, as-of t) | Avoid spending a spectrum on an object already classified by another group — a real, daily operational concern (BTS II: "we avoid duplicating effort") | Reports are semi-structured text with inconsistent names, coordinates, and claims; reconciling "is this the same object, and is that a *classification* or a *discovery*?" needs reading, not regex | Must cite the report id and date ≤ t; coordinate match < 3″ verified by code | `Claim{kind: prior_classification, class, date, source}` → reward for spectrum set to 0 (or reduced per objective); belief gets a near-conclusive class likelihood from a *reported* class via a confusion prior | Extraction accuracy vs TNS ground truth; wasted-spectrum rate with vs without; leakage rate (claims dated > t) must be 0 |
| 2 | **Host & context resolution** (SIMBAD, NED, Sherlock, Gaia, WISE, PS1; literature on the host if famous) | Determine: nuclear or offset? known AGN/QSO? star-like counterpart? host redshift? previous flares? | Catalogs disagree, names collide, "AGN" appears as SIMBAD type, WISE color, or a text note; choosing which cone searches to run and reconciling them is scanner judgement | Each fact must carry catalog id + separation; numeric facts (z, offset) are copied from tool output, never paraphrased | `Claim{host_redshift}` → absolute-magnitude constraint; `Claim{known_agn | star_counterpart | prior_flares}` → contaminant prior; `Claim{nuclear}` → TDE/AGN weighting | Agreement with Sherlock/BTS host fields; downstream calibration gain on contaminants; precision of "known AGN" claims |
| 3 | **Ambiguity investigation** (triggered only when belief entropy is high or templates fit poorly) | Decide what *additional analysis* would resolve an ambiguous candidate and run it (template fit of an alternative class, color evolution, rise-rate, host offset, dust) | Choosing among analyses given a messy dossier is the multi-step reasoning part; the analyses themselves are tools | Budgeted (max tool calls, tokens, $); may only call registered tools; cannot invent measurements | Tool outputs (numeric, typed) enter belief through the pooling layer like any other channel; the LLM's narrative does not | Ablation: fixed-tool-order vs LLM-chosen order vs Jev-routed; resolution rate; cost per resolved candidate |
| 4 | **Hypothesis comparison & dossier** | Produce a structured, evidence-linked comparison of competing explanations for the console and for escalation | Explanation and synthesis are what LLMs are for | Every sentence must reference ledger entries; Jev `Noul` verifies support; unsupported sentences are dropped and counted | Presentation only | Support-verification pass rate; human spot-check of 50 dossiers; corrupted-dossier catch rate |
| 5 | **Literature grounding** (arXiv astro-ph / ADS abstracts) | For rare-class objectives: what signatures are expected and what tests apply | Retrieval + synthesis of prose | May propose *tests* and *priors as named hypotheses*; may not set numeric priors | Proposed tests become tool calls; proposed priors are shown but unused unless a human approves a config change | Relevance judged by Jev `Score` + spot checks; mostly a learning/UX feature, kept small |
| 6 | **Image reading** (cutout triplets) | Real/bogus, nuclear vs offset, host morphology | Multimodal models can read triplets; the question is whether they add anything over BTSbot/ALeRCE stamp classifiers | Output is a typed `Choice`; never a probability into the belief unless it wins the ablation | Pooling channel "image-LLM", weight learned; baseline channel "BTSbot" | AUROC vs BTSbot (public weights) and ALeRCE stamp class on the same alerts; cost/latency |

### A.2 Architecture of the Investigator

```
                      ┌──────────────────────────────────────────────┐
  Snapshot(t)         │               Investigator run               │
  candidate i ───────►│  1. gate      (Jev Noul / entropy / rules)    │
  belief b_i(t)       │  2. plan      (LLM proposes next tool | Jev   │
  objective           │               Choice | fixed order)  [ablate] │
                      │  3. act       tool registry (typed I/O, as-of │
                      │               filter, cache, retries, budget) │
                      │  4. extract   LLM → typed Claim drafts        │
                      │  5. validate  deterministic validators +      │
                      │               Jev support-check  → accept/drop│
                      │  6. ledger    append Evidence + Claims        │
                      │  7. stop?     budget / no new info / resolved │
                      └───────┬──────────────────────┬───────────────┘
                              │ accepted Claims       │ Trace (spans, cost, model ids)
                              ▼                       ▼
                 claim→effect map (code)        console trace view
                 ├ prior_classification → reward adj.
                 ├ host_redshift → abs-mag constraint
                 ├ known_agn / star / flares → contaminant prior
                 └ tool numeric outputs → pooling channel
```

**Orchestration is owned by code**, not by a free-running agent loop: the loop, budgets, stop conditions, and validation are deterministic; the LLM fills three slots (plan, extract, explain), each swappable with Jev or a fixed policy for ablation. This is deliberate: it makes every architectural question an experiment with a baseline rather than a vibe.

**State.** `EvidenceLedger` per candidate: append-only entries `{source, retrieved_at_sim_time, source_date, raw_excerpt_hash, parsed}`; `Claim` entries reference evidence ids; a `Dossier` view is derived, never stored as truth. Cross-night **memory** = ledger persistence + compaction policy (summaries that cite ids; raw retained); staleness rules (re-query TNS nightly; catalogs never). Memory-on vs memory-off is an ablation with cost and error measured.

**Context engineering.** Context packs are assembled by code from the ledger under a token budget, with a relevance pass (Jev `Score` per item vs BM25 vs recency) as an ablation; the evidence card convention (numbers → labeled fields, not prose) from v0 carries over.

**Routing & cascades.** Gate: Jev `Noul("worth investigating given objective")` vs entropy threshold vs always. Planner: Haiku vs Sonnet vs Jev `Choice(next_tool)` vs fixed order. Extractor: Haiku with Sonnet fallback on validator failure vs Sonnet only. Each configuration produces a cost–quality point; the frontier is a headline figure.

**Provenance & validation.** A claim is accepted only if: (a) schema-valid; (b) every cited evidence id exists in the ledger for this run; (c) `source_date ≤ t` (hard leakage check); (d) type-specific checks (coordinate separation computed by code from source coordinates; redshift within [0, 3]; report type ∈ {discovery, classification}); (e) Jev `Noul("the excerpt supports the claim")` ≥ τ or Claude-judge for the ablation arm. Rejections are logged with reasons and are themselves a metric.

**Failure recovery.** Tool errors are typed (`RateLimited`, `Timeout`, `NotFound`, `Malformed`); retries with backoff and jitter; circuit breaker per tool; partial-ledger runs are valid and marked; idempotent re-runs keyed by `(candidate, t, config_version)`; a failure-injection harness (chaos flags per tool) with graded degradation measured in Tier-C evaluation.

**Observability.** One trace per run: spans per tool call and model call, prompt/response hashes, resolved model ids, token and $ ledger, validator outcomes. Stored as JSONL under `runs/`; the console reads it directly.

### A.3 Evaluation of the Investigator (three tiers)
- **Tier A — component, no simulation:** extraction accuracy of prior-classification claims vs TNS/Lasair ground truth (precision/recall at time t); host-context agreement with Sherlock/BTS fields; grounding rate (claims with valid provenance / all claims); **temporal leakage rate (must be 0; any non-zero is a bug, not a result)**; validator rejection reasons distribution; human spot-check of 50 dossiers per milestone.
- **Tier B — decision impact (L0/L1 of the simulation ladder):** belief log-loss/ECE with vs without Investigator claims; selection precision/recall-at-budget; **wasted-spectrum rate** (spectra scheduled on objects already publicly classified at t); regret vs oracle; stratified by candidate difficulty (easy/ambiguous/contaminant).
- **Tier C — architecture ablations:** gate variants; planner variants; extractor cascade; context budget 2k/8k/32k; memory on/off; tool-set subsets; parallel vs sequential tool calls; failure injection at 0/10/30% tool error rate. Reported as cost–quality frontiers with bootstrap CIs over candidates and nights.

### A.4 Where Jev earns (or fails to earn) its place — now four bounded, testable roles
1. **Gate** — `Noul` vs entropy threshold. 2. **Tool router** — `Choice` over tools given a compact ledger state vs LLM planner vs fixed order. 3. **Claim-support verifier** — `Noul` vs Claude-judge vs deterministic-only. 4. **Context relevance scorer** — `Score` vs BM25. Each has a baseline and a cost; Jev's documented numeric weaknesses are irrelevant here because every role is a bounded semantic judgement over pre-structured state, exactly its design envelope. The scanner-classification experiment from Addendum 01 is retained as a fifth, lower-priority role.

### A.5 What I am explicitly *not* adding
No free-running multi-agent swarms, no agent-written code execution, no LLM-generated priors, no "research assistant that writes the paper." Each would add agentic surface without a baseline that could show it helped.

---

## B. Prior-art comparison (papers and code read, not abstracts)

| Dimension | REFITT (Sravan+2020, ApJ) | BTSbot (Rehemtulla+2024, ApJ) | AAS2RTO (Aubert+2025) | RESSPECT (Kennamer+2020; Fink AL loop 2025) | **Cosmic Triage v1** |
|---|---|---|---|---|---|
| Objective | Augment sparse LSST light curves with the most valuable *photometric* epochs for CC-SN inference | Identify bright (m_peak ≤ 18.5) extragalactic transients and trigger SEDM spectra | Rank SNe Ia near peak for small-telescope follow-up | Build the best spectroscopic *training set* for photometric Ia classification (cosmology FoM) | Objective-conditioned follow-up selection under a binding budget, with an evidence-gathering agent |
| Belief / forecast | kNN in ResNet50-CAE embedding over a PLAsTiCC CC-SN library; DTW alignment + GP regression → predicted LC with σ; Bayesian update with a (hypothetical) broker class | Multimodal CNN on 63×63 triplets + 25 alert features → per-alert bright-transient score | SALT2 fit via sncosmo (t₀, phase) or Bazin; redshift fixed from TNS if available | Random-forest committee on Bazin features (QBC) | Broker scores (Fink per-alert, ALeRCE stamp) + calibrated learned pooling; template fit as a *tool*; Investigator claims via code-owned effects |
| Prioritization | Quality score 𝒮 = mean observed error + α·Σ predicted σ; recommend band/epoch when predicted σ > modal training σ **and** the survey won't observe it | Policy rules: ≥2 alerts with score ≥ 0.5 & magpsf ≤ 19 → priority 1; +≥1 alert ≤ 18.5 → priority 2; dedupe vs existing spectrum/classification/trigger | Multiplicative score: x_mag = 10^{0.5(18.5−m)}, x_peak Gaussian(σ=1 d) on t₀, x_rise, x_span, x_vis = altitude integral; greedy, no lookahead | Uncertainty sampling / BatchEntropy / BatchKL under knapsack budget | Direct expected reward (terminal) + one-step EVSI (information actions); CP-SAT schedule |
| Resource model | Observers' "availability and capability" — conceptual in the paper | SEDM queue priority | Per-observatory astroplan visibility; no slew, no Moon | Two telescopes (4 m, 8 m), 6 h each, exposure-time calculator, 2 h cap per object | One modeled facility (extendable), exposure model from SEDM, Moon/altitude, binding budget |
| Autonomy | Fully automated recommendations via REST API | Fully autonomous triggers (>1,200 SEDM requests; first end-to-end automated SN) | Ranked lists per observatory, continuously updated | Recommendations; Fink loop ran live on ANU 2.3 m (92 spectra) | Autonomous in replay; human-in-the-loop console; live mode later |
| Evaluation | LOOCV loss on PLAsTiCC; qualitative simulated LSST night; **no real-outcome evaluation** | Test split: completeness 100%, purity 93% (p2); deployment: 93% real extragalactic transients; ~0.04 d faster than scanners | Archival ZTF 2020–22: 2.08 ± 0.07 SNe Ia/night within ±0.5 d of peak observable by a 1.5 m; 77% of bright good SNe in top-3; mock LSST | SNPCC sims; FoM; AL ≈ random with large initial training, +26% FoM from tiny initial set; real loop: "25% fewer spectra" for same classifier quality | Leakage-safe replay on forward pool vs BTS truth; selection yield; agent Tier A/B/C |
| Key limitations (self-stated) | Simulation-only; CC SN only; library imbalance; no spectroscopy; no scheduling optimization | No LC/redshift input; binary objective; a few host-morphology failures | No lookahead; no slew/Moon; SALT assumed for all; idealized LSST | Feature-extraction uncertainty and labeling failure ignored; batch diversity weak | Investigator decision-impact may be small; spectrum outcomes simulated (ladder L2) |
| Code | Apache-2.0, Python/Poetry, 812 commits, "not meant as a public tool" | MIT; `pip install btsbot`; weights on HuggingFace; training data on Zenodo | CC-BY-4.0; pluggable scoring functions; Fink/ALeRCE/Lasair/ATLAS/TNS clients; astroplan | MIT; Python 3.10+; XGBoost/sklearn; preprocessed inputs | — |

**What we reproduce (and credit):** REFITT's ORACLE decomposition (signal prediction → utility estimation → data acquisition) is exactly our Belief → Value → Schedule and we adopt their framing; BTSbot's policy *is* our "BTS-mimic" baseline and its 25-feature list defines our numeric feature set; AAS2RTO's score is our "AAS2RTO-like" baseline verbatim and its archival-ZTF evaluation is the closest ancestor of our replay; RESSPECT's exposure-time/knapsack cost model and Bazin features; LCO-style ILP scheduling.

**What we change:** explicit objective-conditioned reward + EVSI instead of heuristic scores; a forward-pool, leakage-safe replay scored against BTS truth; and the Investigator — an evidence-gathering agent over text, catalogs, images, and literature with provenance and validation, evaluated by decision impact.

**What is genuinely uncertain:** whether the Investigator changes decisions beyond what deterministic crossmatches (Fink `d:tns`, Sherlock) already provide; whether LLM image reading adds anything over BTSbot; Jev's four roles. **Closest prior art for the agent layer:** RADAR (2026; LLM parsing of GCN circulars into VLA scheduling blocks, GPT-5.5 F₁ 0.89 / Claude Opus 4.7 precision 0.98), ALeRCE's text-to-SQL (2026), AstroAlertBench (2026; LLM alert classification with honesty/calibration gaps). None evaluates an investigator by follow-up decision impact under replay; we don't need that to be novel — it just means there's no benchmark to copy.

**Reusable now:** `btsbot` (baseline + multimodal baseline); aas2rto's broker-client and scoring-plugin patterns (CC-BY); RESSPECT's exposure-time calculator; REFITT's "recommend only where the survey won't observe" rule for the *wait* action; astroplan; sncosmo.

---

## C. Three evaluation assumptions, assessed as open questions

### C.1 Does BTS completeness justify treating absent candidates as non-SNe?
**Partially — only under conditions v0 did not state.** Reading BTS II carefully:
- The 93% (<18.5) / 97% (<18) figures are completeness *of the statistical sample*: events **saved by scanners** that pass **quality cuts** (pre/peak/post-peak coverage with m_lim > 19, ≥ 2 h above 30° within 30 d of peak, not in reference image, A_V < 1) and **purity cuts** (galaxy cross-match or SN-like timescales). About **48% of classified transients fail the quality cuts** — so "not in the quality sample" says nothing about an object's nature.
- The real question is whether bright true SNe exist that scanners *never saved*. BTS II checked all 4,350 TNS transients of 2018–2020 with δ > −30°: 1,015 not in BTS; after cuts, **13 SNe** nominally satisfied selection but were missed (8 at m < 18.5) — ~0.6% of the bright sample — plus 75 that never passed the alert filter for data-quality reasons (reference contamination, single-night coverage, bright stars).
- Therefore the defensible rule is: **a candidate that passes a BTS-alert-filter-equivalent (≥ 2 detections ≥ 30 min apart, high real/bogus, no star-like counterpart < 2″, no bright star < 20″, m ≤ 18.5, |b| outside the plane) and was never saved by BTS is, with ≳ 99% probability, not a classifiable bright SN** — scanners looked and rejected it as AGN/variable/artifact. "Saved but unclassified" (82 of 1,206 bright events in Table 1, ~7%) must be "unknown." **Action:** the Explorer CSV must be pulled *without* quality/purity filters so the full saved list (~10.5k incl. unclassified) is available; verify the unclassified rows are present (M0).
- Base rates matter for metrics: per night, hundreds of alerts pass the filter, ~5–10 are saved, ~3–5 become classified SNe. Negatives dominate; use precision/recall-at-budget, not accuracy.

### C.2 Is ZTF observation availability an adequate weather/availability proxy?
**Partially, for a Palomar-sited facility only.** ZTF is at Palomar; nights with no public alerts (archive file ≈ 74 bytes) are reliable *lost-night* indicators. Gaps: partial nights (use nightly alert volume as a crude clear-hours proxy — crude because ZTF cadence means a given field may simply not be scheduled), instrument downtime of the simulated spectrograph (SEDM has its own), bright-time effects (ZTF observes through full Moon; a spectrograph's Moon-separation limit must be modeled explicitly), and any non-Palomar site (invalid). **Action:** night-level availability from the ZTF record + an explicit, seeded random-downtime fraction (e.g., 10%) as an L1 sensitivity; document that candidate-level "no alert tonight" ≠ clouds.

### C.3 Are there enough representative labels, with clean temporal separation, for calibration and pooling?
**Sufficient for coarse classes; insufficient for rare classes; version drift is the real hazard.**
- Volume: BTS classified ~1,200 bright events in 25.5 months (2018–2020) → ~47/month; a 6-month training window yields ~250–300 bright labeled SNe (~60% Ia, ~25% II, ~8% Ibc, a handful of TDE/SLSN) plus thousands of filter-passing negatives. A log-linear pool over K = 5 coarse classes × ~5 channels (~25 parameters) and per-channel temperature scaling are well-determined; per-class calibration for TDE/SLSN is not → fold them into "other luminous" as planned.
- Separation: strict temporal split (train months ≤ m, evaluate month m+1, rolling origin) uses the data efficiently and matches deployment; no object may appear in both.
- **Drift:** broker classifier versions change (ALeRCE stamp 1.0.0 → 1.0.4 → 2025-beta; Fink science modules evolve). Train and eval windows must share versions, and version fields must be stored per alert (Fink per-alert rows allow it; ALeRCE current-state probabilities do not — another reason the stamp class is used only as a first-alert prior). Seasonal class-mix drift (Galactic plane visibility) is handled by rolling evaluation.
- Label noise: BTS classifications are occasionally revised; snapshot the catalog with a date and keep it fixed per experiment.

---

## D. The console as learning instrument (what changes)
The console keeps everything from v0 §9 and the Addendum (light curves with upper limits, belief bars with evidence-by-channel, Gantt with constraints, policy compare, replay scrubber, simulation badges, "why not?") and adds the Investigator as a first-class view:

- **Investigation trace:** a timeline of the run — gate decision, each tool call (inputs, as-of date, latency, cache hit, cost), each extracted claim with its validator verdicts and the Jev support score, rejections with reasons, and the final accepted claims with their *effects* on reward and belief shown as deltas.
- **Evidence ledger browser:** every source with its date relative to t; a red badge on anything that would have been leakage (should never render — it's a test).
- **Agent-vs-no-agent diff:** for any night, the two schedules side by side with the candidates whose decisions changed, and the Tier-B metric delta so far.
- **Cascade dial:** switch gate/planner/extractor configurations and watch cost, latency, and claim quality move on a live frontier plot.
- **Concept cards** gain the AI-engineering vocabulary alongside the astronomy: provenance, as-of retrieval, calibration vs confidence, cascades, submodular budgets, failure injection.

---

## E. Next implementation plan (no Monday finish line)

Milestones are ordered so each produces a standalone measured result and so the objective downstream metric exists *before* any agent is built — otherwise the agent's value is unmeasurable and the project drifts toward demo-ware.

| M | Scope | Standalone result | Learning focus |
|---|---|---|---|
| **M0 — kill-tests (1–2 days)** | Data/tool access: TNS path (bot or Lasair/Fink TNS tables), Lasair token + Sherlock, ALeRCE stamps, SIMBAD/NED via astroquery, Fink POST, BTS full CSV incl. unclassified, forward-pool volume, budget-binding check; Jev + Claude keys; `btsbot` install; ZTF-band sncosmo smoke test | Go/no-go table | APIs, rate limits, data contracts |
| **M1 — substrate (week 1)** | Contracts; ingest + cache; `Snapshot(t)` with leakage tests; belief v0 (broker scores → calibrated pool); reward tables O1/O4; CP-SAT scheduler + feasibility checker; replay over forward pool; baselines (random, brightest, broker-greedy, AAS2RTO-like, BTS-mimic, oracle); console v0 | Policy comparison table with CIs; calibration plot | Bayes, calibration, optimization, experimental design (the astronomy/probability half of your goals) |
| **M2 — Investigator v1 (weeks 2–3)** | Tool registry (TNS/report lookup, SIMBAD, NED, Sherlock, alert history, cutouts, dust, offset/abs-mag calculators, template-fit tool); typed claims + validators + provenance; code-owned loop with budgets; single model (Sonnet); evidence ledger; traces; console trace view; **Tier A eval** | Extraction/grounding accuracy table; leakage = 0 proof; cost per candidate | Tool calling, structured outputs, validation, observability |
| **M3 — decision impact (week 4)** | Claim→effect map; Tier B with vs without Investigator, stratified by difficulty; wasted-spectrum metric | **Headline: does the agent change decisions, where, at what cost** | LLM + deterministic integration; honest evaluation |
| **M4 — routing & cascades (weeks 5–6)** | Jev gate / router / verifier / relevance; Haiku→Sonnet→Opus extractor cascade; option-order stability; context-budget sweep; Tier C frontiers | Cost–quality frontier figure | Specialized models, routing, context engineering |
| **M5 — state & reliability (week 7)** | Cross-night ledger + compaction; staleness policy; failure-injection suite; idempotent re-runs | Memory on/off and chaos-degradation curves | Memory/state, failure recovery |
| **M6 — multimodal (week 8)** | Cutouts → Jev-1.14 / Claude vision vs `btsbot` vs ALeRCE stamp; pooling-weight verdict | AUROC/cost table | Multimodal where it fits |
| **M7+ — depth** | sncosmo likelihood engine as a full belief channel; EVSI for wait/photometry; second facility; Rubin stream; live mode with nightly plan email; write-up | — | Optional scientific depth |

**Highest-value experiments, in order:** (1) M3 decision impact — the result everything else hangs on; (2) M4 cascade frontier — the most transferable agent-engineering lesson; (3) M2 leakage-safe grounding — the discipline most agent projects skip; (4) M5 memory/chaos — reliability engineering with numbers; (5) M6 multimodal vs BTSbot — a clean, honest head-to-head.

**Recommended first vertical slice (end of M1 + a thin M2 spike):** one candidate, one night: forward pool → calibrated belief → scheduled or not → *then* a single Investigator run on that candidate showing a TNS/Sherlock lookup turning into a validated claim and a reward delta, with the trace in the console. That slice touches every layer, teaches both halves, and is honest about what is and isn't measured yet.

---

## Open questions for you
1. Approve the re-centering (F.4) and the ~65/35 balance. Specifically: physics-template likelihoods demoted to a tool and M7, broker scores + calibration as the M1 belief source.
2. TNS access: if an individual bot isn't permitted, the fallback is Lasair/Fink TNS crossmatch tables (classification dates may be partial). Acceptable to start there?
3. Model budget: cascades need real spend to measure; a rough ceiling per month helps me size M4.
4. Do you want the EDGAR alternative kept as a documented "road not taken" in the architecture, or dropped?
