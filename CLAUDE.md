# Cosmic Triage — instructions for the implementing agent

**Source of truth:** `docs/ARCHITECTURE.md` (v1). Read it fully before any work. `docs/REVIEW-02.md` and `docs/REVIEW-01-addendum.md` are rationale/history only — do not implement from them. Do not create new architecture documents; write milestone reports to `runs/reports/M<N>.md`.

## Workflow
- Work one milestone at a time (`ARCHITECTURE.md` §10.3). Start by restating the milestone's completion criteria, then implement, then run `scripts/accept_M<N>.py`, then write the report.
- Two tracks: anything under `runs/exploratory/` is demo-only and must never feed a benchmark table (§10.1).
- **Stop and ask** — do not proceed unilaterally — on any trigger in §14. Record the question under "Needs architecture decision" in the milestone report.
- Record every other non-obvious choice under "Decisions made" in the report.

## Hard rules (from §1.4, §13.2)
- Hypotheses are generated; probabilities are computed. No LLM/Jev output touches a probability or reward except via a validated `Claim` → `ClaimEffects` or a learned pool weight.
- No network in tests (`COSMIC_OFFLINE=1`; recorded fixtures in `tests/fixtures/`). Never weaken, skip, or delete a test to pass.
- Only `replay` may read truth labels or future-dated data; everything else consumes `Snapshot(t)`.
- Every run logs `seed`, `config_hash`, resolved model ids, tokens, USD; identical inputs must produce identical output hashes.
- Jev is never used for arithmetic, counting, dates, or raw light-curve numbers; randomize `Choice` option order and log it.
- Results before pixels: console work is time-boxed and follows a measured result. The Night Theater (§8.2) is a first-class demo requirement but a *player* of replay artifacts only — no UI-side science, and simulated activity always rendered distinctly with its L-badge.

## Commands
- `uv sync` · `uv run pytest` · `uv run ruff check .` · `uv run mypy src/cosmic_triage/contracts src/cosmic_triage/investigator`
- `uv run python scripts/m0_killtests.py` · `uv run python scripts/demo_investigate.py <OID> <MJD>` · `uv run python scripts/accept_M<N>.py`
- Console: `cd console && npm install && npm run dev` (API: `uv run uvicorn cosmic_triage.api.app:app --reload`)

## Secrets
`.env` only (see `.env.example`). Scrub headers when recording fixtures.
