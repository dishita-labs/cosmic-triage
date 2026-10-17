# Cosmic Triage — Architecture Review Addendum 01

> **Historical.** All accepted conclusions here are folded into `ARCHITECTURE.md` v1 (authoritative). Some specifics were further revised by `REVIEW-02.md` (notably: template-likelihood engine demoted to a tool, project re-centered on the Investigator, milestones replaced by M0–M7). Do not implement from this file.

*2026-10-17. Responds to six reviewer concerns against `ARCHITECTURE.md` v0. Sections of v0 that this addendum supersedes are marked there inline. No code has been written.*

## Verdict summary

| # | Concern | Verdict | One-line conclusion |
|---|---|---|---|
| 1 | VOI formulation | **Agree** | v0 conflated three quantities. Spectra are *terminal* actions with direct reward, not information; only photometry and *wait* carry information value, and that value is EVSI (decision-relative), not entropy reduction. Reformulated as a budgeted sequential decision problem. |
| 2 | Jev + Bayes double counting | **Agree — and it's worse than stated** | The same error already existed in v0 between Fink light-curve scores and sncosmo likelihoods. Fix: partition evidence by channel, pool with learned log-linear weights, calibrate every source before pooling. |
| 3 | Replay integrity | **Agree strongly** | Biggest gap in v0: the truth set (BTS) is *endogenous to the BTS-rule baseline*, and the cohort was selected using future information. Fix: forward candidate pool, score only in the bright regime where BTS is ~93–97% complete, time-split training, explicit "unknown" accounting. |
| 4 | Simulated observations | **Partially agree** | Dependency is real but smaller than it looks: the headline *selection-quality* metric can be computed from truth alone. A four-level "simulation dependency ladder" labels every metric. |
| 5 | Sequencing | **Agree** | v0 Tier 1 was overpacked. Resequenced around three questions — *Can we believe? Can we choose? Can we explain?* — with the console as a day-one instrument, Jev moved to week 2 for methodological (not priority) reasons. |
| 6 | Feasibility & baselines | **Partially agree** | Sufficient for the core question *if* three things are verified first: forward-pool volume, that the follow-up budget is actually binding in replay (otherwise all policies converge), and statistical power over the window. TDE/SLSN/contaminant modeling gaps acknowledged. |

---

## 1. Value of information — what v0 got wrong and the corrected formulation

### 1.1 The error
v0 §4.2 step 4 wrote EVOI as "E_y[U(decide | b′(y))] − U(decide | b)" and in the same breath described "utility-weighted EIG". Those are three different objects:

| Quantity | Definition | Properties | Where it belongs |
|---|---|---|---|
| **Expected information gain (EIG)** | I(C;Y) = H[b] − E_y H[b′(y)] | ≥ 0; objective-agnostic; in nats; blind to whether the information *changes any decision* | **Diagnostic only** (UI, learning). Not an objective. |
| **Expected value of sample information (EVSI)** | E_y[max_d E_{c∼b′(y)} U(d,c)] − max_d E_{c∼b} U(d,c) | ≥ 0; zero when no outcome would change the downstream decision; needs a *downstream decision* d | Value of **information actions**: targeted photometry, *wait* |
| **Direct expected reward** | E_{c∼b}[R(a, c, φ)] | the scientific deliverable itself | Value of **terminal actions**: classification spectra |

"Utility-weighted EIG" is not a decision-theoretic quantity; it rewards resolving distinctions no objective cares about and ignores that information is only valuable if a slot exists to act on it.

### 1.2 The key realization: a classification spectrum is a terminal act
For O1/O4 the spectrum *is* the deliverable — a pre-peak spectrum of a SN Ia is the thing the program exists to obtain. Its value is R(class, phase), not "entropy removed." So the per-night problem is a **stochastic knapsack over expected rewards**, with beliefs b_i supplying the probabilities. That is already what the field does implicitly (b ≈ "SN-like score", R ≈ brightness); our contribution is making b calibrated and R explicit and objective-conditioned.

Information has value in exactly two places:
1. **Photometry/wait → tomorrow's spectra.** A free survey point or a cheap imaging epoch sharpens b_i so tomorrow's knapsack is better. That is textbook EVSI with d = "tomorrow's allocation."
2. **Timing (optimal stopping).** Spectrum *now* (lower b, earlier phase, higher R if pre-peak matters) vs *tomorrow* (sharper b, but phase advances, target may fade, weather/visibility risk). Each candidate is a stopping problem; the budget couples them.

### 1.3 Corrected formulation
State S_t = {b_i(t), φ̂_i(t), m̂_i(t)} for all candidates; action = tonight's feasible schedule A_t; reward r_t = Σ_{spectra in A_t} R(c_i, φ_i) realized from truth; transition = real survey photometry + our observations. Objective: maximize E[Σ_t r_t] over the window. This is a finite-horizon POMDP — intractable exactly, so we use a hierarchy of approximations that *is itself an ablation axis*:

- **L0 Myopic-direct:** maximize Σ_i E_{b_i}[R] · x_i tonight, s.t. constraints. (Weekend.)
- **L1 One-step lookahead:** value(a) = E_{b}[R(a)] for terminal a; value(a) = EVSI₁(a) for information a, where tomorrow's value is approximated by tomorrow's L0 allocation over posterior-predictive samples (5–20 samples per candidate suffice at our scale). Includes *wait* with cost 0 and a phase-decay penalty. (Week 2.)
- **L2 Rollout:** 2–3-night Monte-Carlo rollout with L0 as the base policy, for the stopping tradeoff. (Tier 2.)

Reward tables R(objective, class, phase_bin) are hand-written, versioned, and frozen before any comparison. For O3 (rare objects) R is not additive — the 2nd TDE is worth less than the 1st — so O3 needs a submodular/diminishing-returns term; CP-SAT handles it with piecewise-linear count penalties. Flagged, not weekend scope.

### 1.4 Worked numerical example
Objective O1. Reward of a spectrum: normal Ia pre-peak = 1.0; Ia post-peak = 0.3; any non-Ia SN = 0.1; contaminant (AGN/CV/star) = 0. One spectrograph slot tonight and one tomorrow.

- Candidate **A**: b_A = {Ia 0.55, II 0.30, contaminant 0.15}; ~3 d pre-peak; 80% chance still pre-peak tomorrow.
- Candidate **B**: b_B = {Ia 0.80, II 0.15, cont 0.05}; at peak tonight; certainly post-peak tomorrow.
- Candidate **C** (available tomorrow only): expected reward 0.50.

**Direct expected rewards tonight:** E[R_A] = 0.55·1 + 0.30·0.1 = **0.58**; E[R_B] = 0.80·1 + 0.15·0.1 = **0.815**.
Plan "B tonight, A tomorrow": 0.815 + [0.55·(0.8·1 + 0.2·0.3) + 0.30·0.1] = 0.815 + 0.503 = **1.318**.
Plan "A tonight, B tomorrow": 0.58 + [0.80·0.3 + 0.015] = 0.58 + 0.255 = 0.835. → B tonight. Phase decay, not entropy, drives this.

**Now add a free ZTF r-band point on A tonight.** Posterior-predictive: P(point "looks Ia-like" | Ia) = 0.7, | II = 0.3, | cont = 0.2.
P(Ia-like) = 0.55·0.7 + 0.30·0.3 + 0.15·0.2 = 0.505.
- If Ia-like: b′_A = {0.762, 0.178, 0.059}; E[R_A tomorrow] = 0.762·0.86 + 0.018 = **0.673** > C's 0.50 → observe A.
- If not: b′_A = {0.333, 0.424, 0.243}; E[R_A] = 0.333·0.86 + 0.042 = **0.329** < 0.50 → observe C instead.
Tomorrow's expected value with the point = 0.505·0.673 + 0.495·0.50 = 0.587; without it = max(0.503, 0.50) = 0.503. **EVSI = 0.084** reward units.

**EIG of the same point:** H[b_A] = 0.975 nats; E[H[b′_A]] = 0.505·0.681 + 0.495·1.074 = 0.876; **EIG = 0.099 nats.**

**Why the distinction matters:** change C's expected reward to 0.70. Now in *both* branches tomorrow's best pick is C (0.673 < 0.70 and 0.329 < 0.70), so the point can't change the decision: **EVSI = 0**, while **EIG is still 0.099**. An entropy-driven planner would spend effort learning about A for no scientific return. EVSI knows about the alternative; EIG does not.

**Recommendation:** adopt §1.3. Keep EIG as a displayed diagnostic ("how much did we learn") because it is a good teaching quantity, and because *predicted-vs-realized EIG* on real survey photometry is a simulation-free test of our likelihood model (see §4).

---

## 2. Jev, Fink, and double counting

### 2.1 The problem is real and pre-exists Jev
v0 proposed beliefs = sncosmo template likelihoods × "priors from Fink alert-time scores + stamp class," with Jev as "one more likelihood term." Fink's SuperNNova/RF scores are *functions of the same photometry* the templates see; Jev's evidence card would verbalize that photometry again. Multiplying them as if conditionally independent is the naive-Bayes-on-correlated-features error and produces overconfident posteriors — which would then be *rewarded* by a myopic knapsack that loves sharp beliefs. The failure would be invisible without a calibration check.

### 2.2 Integration methods considered
| Method | Handles correlation? | Data needed | Interpretable? | Verdict |
|---|---|---|---|---|
| Naive product of likelihoods | No | none | yes | **Reject** |
| Tempered product (each source^α, Σα=1 — logarithmic opinion pool) | Crudely | small (tune α by log-loss) | yes | Acceptable fallback |
| Stacking: logistic regression on sources' log-probabilities, fit on held-out nights | Yes, empirically | hundreds of labeled candidate-epochs (we have thousands in the bright regime) | yes (weights) | **Adopt** |
| Mixture-of-experts gating | Yes | more | medium | Tier 2 if stacking plateaus |
| Jev as gate only (never a likelihood) | n/a | none | yes | **Adopt as Jev's fallback role** |

### 2.3 Recommended design: channel partition + learned pooling + calibration
1. **Each raw evidence channel feeds exactly one model** (minimizes overlap by construction, and gives the UI an honest "evidence by channel" breakdown):
   - Photometry (detections + upper limits) → template likelihoods only.
   - Stamp images → broker stamp classifier (first alert) only.
   - **Semantic context** (Sherlock host association text, SIMBAD/CDS cross-match type, Galactic latitude band, TNS/AstroNote text if any) → scanner (rules / GBM / Jev / Claude).
   - Variability history (ndethist, long-baseline stochasticity) → contaminant feature model.
2. **Calibrate each source** against BTS truth on training nights (temperature scaling or isotonic per class). Jev's probabilities are documented as a ranking signal, not calibrated — this step is mandatory for it, and we will show its reliability diagram before and after.
3. **Pool with a log-linear model** (multinomial logistic regression over per-source log-probs, L2-regularized), fit on *training nights strictly before the evaluation window*. The learned weights are the ablation: if Jev's weight → 0 when the GBM on the same context features is present, Jev adds nothing.
4. **Report ECE and log-loss of the pooled posterior per epoch**, with a hard gate: a configuration that is less calibrated than template-only is not allowed into policy comparisons.
5. **Fink light-curve scores are moved out of the belief pipeline** into (a) a baseline policy ("broker-greedy") and (b) an alternative *cheap* belief configuration (Fink-only, no templates) to ablate whether physics templates earn their compute. Never both in the same posterior unless via the learned pool.

### 2.4 Two Jev configurations, to locate where any value comes from
- **Jev-context:** card contains *only* semantic context — no light-curve statements. Tests the hypothesis that Jev reads host/catalog semantics numeric models ignore.
- **Jev-full:** card adds verbalized light-curve summaries ("rose 0.8 mag in 2.1 d"). If Jev-full beats Jev-context but adds nothing over templates in the pool, Jev's apparent value was redundant photometry.
- Both run with Choice-option order randomized across calls (documented first-option bias) and the flip rate reported.

---

## 3. Historical replay integrity

### 3.1 Agree, and the gap is larger than described
Four leakage/bias channels in v0, in order of severity:

**(a) Endogenous truth set.** BTS *is* the output of the BTS selection rule (m ≤ 18.5–19, SN-like, extragalactic) plus scanner judgement. If positives = "in BTS," then the BTS-rule baseline recovers them nearly by construction, and any policy that selects a bright object *not* in BTS is penalized even if it was a real SN that BTS happened to miss. The evaluation would quietly reward imitating BTS. **This is the most serious flaw in v0.**

**(b) Retrospective cohort.** v0 built the cohort from BTS objects "peaking in the window" plus contaminants chosen by their *final* ALeRCE classes. Both use future information: membership in the pool leaks "this becomes a classified SN," and `peakt` is unknowable at the time.

**(c) Training leakage.** Any learned component (GBM scanner, pooling weights, calibration maps) fit on data overlapping the evaluation nights.

**(d) Field-level leakage** (minor): ALeRCE `corrected` magnitudes and final `drb` versions; window chosen with knowledge of BTS coverage.

### 3.2 Fixes
1. **Forward candidate pool, built per night without reference to class or outcome.** Pool(n) = ALeRCE objects with `firstmjd` in [n−14, n] ∩ a cheap, time-honest pre-filter shared by *all* policies (e.g., ≥ 2 detections, `drb` ≥ 0.5 on first alerts, `ndethist ≤ ndet + k` i.e., genuinely new, stamp-classifier SN prob ≥ 0.1 — the stamp classifier runs on the first alert so it is time-honest). Policies then triage *within* the pool. Pool volume per night is **kill-test #2** (expected hundreds; manageable with caching).
2. **Score only in the regime where truth is near-complete.** BTS II reports 97% completeness below 18 mag, 93% below 18.5, 75% at 19. Therefore: a pool object with observed peak ≤ 18.5 that is *not* in BTS is, with ≳ 90% probability, not a classifiable SN — the proxy "contaminant" label becomes defensible *only there*. Candidates fainter than 18.5 are kept in the pool (they consume slots and model attention) but **outcomes on them are scored as "unknown"** and reported separately, never as 0 reward silently. Sensitivity analysis: score unknowns as (i) 0, (ii) ALeRCE final class as weak truth, (iii) excluded; conclusions must hold under all three.
3. **The facility's magnitude limit is set to match the scored regime** (spectrograph effective limit ≈ 18.5–19 for a 30–40 min exposure, per SEDM), which is physically natural and aligns incentive with measurability.
4. **Strict temporal splits.** Train/calibrate/pool-fit on nights before the evaluation window (e.g., 2025-03 → 2025-08); evaluate on 2025-09 → 2025-11 (or longer, see §6). No cross-validation that mixes nights.
5. **`Snapshot(t)` denylist** retained from v0 and extended: `peakt, peakmag, peakabs, type, redshift, class, probability (lc_classifier), ndethist/ncovhist as of final` — the latter two are recomputed from detections ≤ t.
6. **Weather from the record, not a model.** Palomar's actual photometric nights are encoded in whether ZTF produced alerts that night (public archive file size; ALeRCE detection counts). Our simulated Palomar facility loses exactly the nights ZTF lost. One less simulation.
7. **BTS-rule baseline is retained but relabeled "BTS-mimic (truth-correlated)"** and reported with the caveat. The *fair* strong baseline becomes broker-greedy × brightness (closest approximation of BTSbot's deployed behavior we can replay).

---

## 4. Simulated observations — the dependency ladder

### 4.1 Partially agree
The reviewer is right that v0 didn't separate empirical from simulated. But the separation turns out favorable: if the headline metric is **selection quality against truth** — "of the targets a policy scheduled (feasibly) tonight, how many were truly objective-relevant at that phase" — then the *reward is computed from BTS truth and the real light curve's peak time*, and no simulated spectrum result enters it. The spectrum-outcome model (confusion matrix) is then a component of the *policy's* world model (how it expects beliefs to update) and of multi-night belief dynamics, not of the score.

### 4.2 Ladder (every reported number carries a level)
| Level | Depends on | Metrics at this level |
|---|---|---|
| **L0 — none** | real photometry, real truth, real geometry | belief calibration (log-loss/Brier/ECE per epoch); scanner AUROC; **predicted vs realized EIG on real next ZTF points**; schedule feasibility; **selection precision/recall-at-budget vs truth, with phase from the true light curve** |
| **L1 — physical models we parameterize, not invent** | exposure-time model (SEDM paper), facility magnitude limit, weather from the ZTF record | objective yield per spectrograph-hour; utilization; regret vs oracle |
| **L2 — reveal noise** | confusion matrix (from the 4,646-spectra study) applied when a spectrum updates beliefs | multi-night belief trajectories; number of *re-observations* triggered |
| **L3 — synthetic photometry** | posterior-predictive draws for requested imaging at times ZTF didn't observe | targeted-photometry EVSI policies (Tier 2) |

Rule: L0 and L1 results are the claims; L2 results require a sensitivity sweep (perfect / 90% / 80% reveal) and must be stable; L3 results are labeled "simulation study" in every table and in the UI (badge on every synthetic point).

### 4.3 A hidden L1 assumption worth naming
The follow-up budget size. If we allow 12 spectra/night and only 4 bright SN-like candidates exist, every policy picks all four and the comparison is vacuous (§6.3). The budget must be chosen to be *binding* — and chosen before results, from pool statistics, not tuned afterward.

---

## 5. Sequencing — resequenced around three questions

### 5.1 Agree: v0 Tier 1 was overpacked
Honest estimate of v0's weekend list: ingest + leakage-safe snapshot + sncosmo belief engine with grid marginalization + calibration study + reward tables + EVSI + CP-SAT + feasibility checker + replay loop + 8 policies + evidence cards + GBM + Jev + Claude + stability tests + web console. That is 2–3 weeks of focused work for one engineer with an agent, not 2.5 days — mostly because of debugging the belief engine on real sparse data and the leakage audit, both of which resist acceleration.

### 5.2 Why Jev moves to week 2 (methodological, not priority)
Evaluating Jev *properly* (§2) requires: a calibrated template-only posterior to compare against, a trained GBM on identical features, held-out night splits, and the pooling layer. All of that is the replay harness. Testing Jev before the harness exists would produce exactly the kind of uncontrolled "it seemed to help" result the brief forbids. The *API spike* (one call, latency, token count) stays in Saturday's kill-tests so there are no integration surprises.

### 5.3 Revised sequence
Each stage ends in a result that stands on its own and a console view that teaches it.

**Stage 0 — Kill-tests (Sat AM, ≤ 3 h).** See §6.4. Any failure re-plans before more code.

**Stage 1 — "Can we believe?" (Sat–Sun).**
Scaffold; typed contracts; ALeRCE/BTS/Fink clients with a parquet cache; forward pool for a short window (10 nights) to check volumes; `Snapshot(t)` with leakage tests; template likelihood engine (precompute each template's ZTF g/r/i light curve on a phase grid once; likelihoods become vector ops over a t₀ × amplitude × E(B−V) grid; censored likelihood for upper limits); contaminant feature model; pooled posterior with calibration.
**Result:** log-loss/Brier/ECE vs days-since-first-detection, template-only vs stamp-prior vs pooled, against BTS truth in the bright regime. **(L0.)**
**Console v0:** light curve with upper limits and posterior-predictive bands per class, belief bars, entropy, concept cards for magnitudes/upper limits/Bayes/calibration. This view is needed to debug beliefs anyway — the dashboard starts as the instrument.

**Stage 2 — "Can we choose?" (Mon + next session).**
Reward tables O1/O4 (frozen); L0 myopic policy; astroplan visibility → CP-SAT with independent feasibility check; replay loop over the forward pool; baselines: random, brightest-first, broker-greedy×brightness, BTS-mimic (caveated), oracle.
**Result:** selection precision/recall-at-budget and yield per spectrograph-hour, paired over nights with bootstrap CIs; regret vs oracle. **(L0/L1.)**
**Console v1:** night sky/altitude plot, Gantt with per-target expected reward, constraint toggles with live re-solve, policy side-by-side.

**Stage 3 — "Can we explain, and does information pay?" (week 2).**
L1 one-step EVSI for *wait* and (L3) targeted photometry; predicted-vs-realized EIG on real survey points; evidence cards; GBM, Jev-context, Jev-full, Claude-structured scanners; pooling weights and verdicts per §2; Jev gate vs entropy gate.
**Result:** the Jev ablation table with pre-registered verdicts; EVSI vs myopic. **Console v2:** decision-trace drawer, "why this / why not that," Claude narratives verified by Jev Noul, replay scrubber.

**Stage 4 — Depth (weeks 3+).** Fink Tier-2 replay; Avro Tier-3 for 3 nights with cutouts (Jev-1.14 image experiment); L2 rollout for stopping; second facility; O2/O3 with submodular rewards; longer windows for power; live mode.

**Monday's honest deliverable:** Stage 1 complete with its calibration result and console v0, Stage 2 started (pool + visibility + CP-SAT toy running). That is a meaningful scientific milestone — *we will know whether beliefs are informative*, which is the assumption everything else rests on.

---

## 6. Feasibility, baselines, and what to test first

### 6.1 Datasets — sufficient with the §3 fixes, two gaps noted
- BTS truth is adequate **in the bright regime only**; this bounds the science claim to "spectroscopic-reach triage," which is exactly the operational problem anyway.
- **Statistical power is the quiet constraint.** BTS classifies roughly 3–5 SNe/night; ~60% are Ia; perhaps half are caught pre-peak → **~1–2 O1-relevant events per night**. Over 60 nights that is ~100 events; differences of a few points between decent policies will be inside the CIs. Plan for a **120–180-night evaluation window** (two seasons) or several disjoint windows; the forward pool and caching must be sized for that. This is kill-test #3.
- Classification *dates* (when humans knew) remain unavailable without a TNS bot; the "beat the humans to it" metric stays deferred.

### 6.2 Light-curve models — gaps and workarounds
- sncosmo covers SN Ia (SALT3, Hsiao), SN II / IIb / Ib / Ic / Ic-BL (Vincenzi+19), SN IIn and SLSN via a few older templates; ZTF `ztfg/ztfr/ztfi` bandpasses are built in. **TDE and SLSN-I have thin or no template coverage** → weekend K folds TDE/SLSN into "other luminous transient" via a parametric Bazin/blackbody model; proper treatment in Stage 4 (relevant for O3 anyway).
- **Contaminants (AGN, CV, stars) have no physical templates**; they are handled discriminatively from history features. Mixing a generative likelihood with a discriminative probability is only coherent through the calibrated pooling layer (§2) — another reason that layer is mandatory, not optional.
- Distance is unknown at decision time; a per-class **peak absolute-magnitude prior** converts apparent brightness into a crude phase/distance constraint. Milky Way extinction from `dustmaps` (SFD), not from the BTS `A_V` column.
- **Compute:** ~67 CC templates + Ia + parametric, × grid (t₀: 40 × amp: 30 × E(B−V): 5 = 6k points) × ~30 photometric points → ~10⁷ flops per candidate-epoch; trivial if template fluxes are precomputed on a phase grid. The naive approach (calling `sncosmo.fit_lc` per candidate per epoch) is **not** viable at pool scale and would have sunk the weekend.

### 6.3 Baselines — one change, one addition
- **Change:** BTS-rule → "BTS-mimic (truth-correlated)," caveated (§3.2.7).
- **Addition:** **broker-greedy × brightness × visibility** as the primary fair baseline (closest replayable proxy for deployed BTSbot behavior), and **"template-only L0"** as the internal baseline every AI-assisted configuration must beat.
- Oracle remains for regret.
- **Budget must bind.** Pre-register the nightly budget from pool statistics so that median (bright SN-like candidates per night) / (slots) ≥ 2. If the real sky doesn't supply enough bright candidates to make a 1-spectrograph budget binding, shrink the budget (3–4 spectra/night, i.e., a small-telescope program) rather than inflate the pool with faint unscoreable objects.

### 6.4 Kill-tests, re-ordered by what they can invalidate (Saturday, ≤ 3 h)
| # | Test | Invalidates if it fails | Time |
|---|---|---|---|
| 1 | Template likelihoods on 30 BTS objects truncated at +2/+5/+10 d: log-loss vs class-frequency prior, and vs stamp prior | the belief engine, hence the decision layer (fall back to broker-score beliefs) | 90 min |
| 2 | Forward pool volume: ALeRCE `/objects?firstmjd∈night` with the time-honest pre-filter, for 5 nights | API feasibility; pool size vs budget | 20 min |
| 3 | Scarcity & power: count pool objects with peak ≤ 18.5 and in BTS per night over the candidate window | whether the budget binds; window length | 20 min |
| 4 | Fink `/objects` POST returns per-alert `d:*` scores + upper limits | replay-safe ML priors (degrade to stamp prior + templates) | 10 min |
| 5 | Precomputed-template likelihood speed: 1 candidate-epoch × full grid < 50 ms | pool-scale replay compute | 20 min |
| 6 | CP-SAT: 60 targets × 12-h night × intervals solves < 5 s | scheduler choice (fallback: greedy by expected reward) | 20 min |
| 7 | Jev: key, one `system_one` call with a ~500-token card, latency & tokens logged | Stage 3 integration (architecture unaffected) | 15 min |
| 8 | ALeRCE `/objects` class/probability filter quirk | cohort/pool query path | 10 min |

---

## 7. Preserving the learning dashboard and demo ambition

The resequencing *strengthens* the console rather than deferring it: it becomes the instrument we debug with from Stage 1, and each stage adds the view that teaches that stage's concept. Three additions prompted by this review:

- **Simulation badges everywhere.** Every number and every plotted point carries its ladder level (L0–L3) so you can never mistake a synthetic photometry draw or a simulated reveal for data.
- **Evidence-by-channel view.** Because evidence is partitioned (§2.3), the belief panel can show how much each channel moved the posterior — photometry, stamp, context, history — and, in Stage 3, what Jev vs GBM said about the same card.
- **"Why not?" explanations.** For any unselected target, the trace shows whether it lost on expected reward, on phase, on feasibility (altitude/Moon/exposure), or on budget — the EVSI example in §1.4 is the archetype of what this view explains.

Concept cards expand to cover the ideas this review surfaced: EVSI vs EIG, optimal stopping, opinion pools and calibration, selection bias and completeness, simulation dependency.

---

## 8. Open questions for you

1. **Scoring regime.** Do you accept restricting scored outcomes to peak ≤ 18.5 (where BTS is ≥ 93% complete), with fainter outcomes reported as "unknown" under three sensitivity treatments? This bounds the claim to spectroscopic-reach triage.
2. **Budget.** A binding budget may mean modeling a *small* program (3–4 spectra/night) rather than SEDM-scale. Is a small-telescope framing acceptable? It is arguably the more interesting resource problem anyway.
3. **Monday scope.** Stage 1 complete (calibration result + console v0) and Stage 2 started. Confirm that this replaces v0's Tier 1 definition of done.
4. **Window length.** 120–180 evaluation nights across two seasons for statistical power — more API fetching and caching up front. OK?
5. **O3 (rare objects).** Keep as Stage 4 with submodular rewards, or drop until O1/O4 results exist?

## 9. Changes to `ARCHITECTURE.md` v0 (marked inline there)
- §4.2 step 4 and §6 "EIG" rows → superseded by Addendum §1 (direct reward + EVSI; EIG diagnostic only).
- §4.3 and §5.2(1) "Jev as likelihood term" → superseded by Addendum §2 (channel partition + learned pooling + calibration; two Jev configurations).
- §4.2 step 3 "priors from Fink alert-time scores" → removed from belief pipeline; Fink becomes a baseline and an alternative cheap belief configuration.
- §7.1 cohort construction → superseded by Addendum §3.2 (forward pool; bright-regime scoring; temporal splits; weather from record).
- §8.2 baseline 3 → "BTS-mimic (truth-correlated)"; broker-greedy × brightness promoted to primary fair baseline.
- §8 metrics → every metric carries a simulation level (Addendum §4.2).
- §10 Tier 1 → superseded by Addendum §5.3 stages.
- §11 kill-tests → superseded by Addendum §6.4 ordering and additions (#2, #3, #5).
