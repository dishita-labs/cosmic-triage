// Thin client for the console API. The console never computes science; it renders replay artifacts.
import type { CandidateState, NightFrame, TheaterNight } from "../types/contracts";

export interface RunInfo {
  run_id: string;
  mode: "bench" | "exploratory";
  config_hash: string;
  seed: number;
  output_hash: string;
  code_version: string;
  nights: string[];
}

/** Per-night pool summary written by scripts/run_m1_spine.py (derived from Snapshot(t), all values <= t). */
export interface PoolCandidate {
  oid: string;
  ra: number;
  dec: number;
  gal_b: number;
  first_detection_mjd: number;
  last_detection_mjd: number;
  n_detections: number;
  n_nondetections: number;
  brightest_mag: number;
  latest_mag: number;
  latest_band: string;
  fink_snn_snia_vs_nonia: number | null;
  fink_cdsxmatch: string | null;
  fink_tns_alert_time: string | null;
}

export interface PoolNight {
  night: string;
  t_mjd: number;
  candidates: PoolCandidate[];
}

export interface TheaterNightRef {
  run_id: string;
  night: string;
  mode: "bench" | "exploratory";
  config_hash: string;
  n_candidates: number;
  n_frames: number;
}

export interface TheaterData {
  header: TheaterNight;
  frames: NightFrame[];
}

export interface InvestigationSummary {
  run_id: string; oid: string; t_mjd: number; night_id: string; mode: string; outcome: string; stop_reason: string;
  cost_usd: number; within_budget: boolean; label: string | null; n_claims: number; n_evidence: number; n_rejected: number;
}

interface SpanRow {
  span_id: string; parent_id: string | null; kind: string; name: string; status: string; latency_ms: number | null;
  model_id: string | null; usd: number; cache_hit: boolean | null; error: string | null; attrs: Record<string, unknown>;
}

interface Check { name: string; passed: boolean; detail: string }

export interface InvestigationDetail {
  header: {
    run_id: string; oid: string; t_mjd: number; night_id: string; mode: string; outcome: string; stop_reason: string;
    config_version: string; seed: number; output_hash: string; cost_usd: number; counters: { tool_calls: number };
    effects?: { spectrum_reward_factor: number; log: { claim_kind: string; status: string; factor: number | null }[] };
  };
  spans: SpanRow[];
  evidence: { id: string; source: string; source_date: number | null; dt_days: number | null; leak: boolean; parsed: Record<string, unknown> }[];
  claims: { kind: string; payload: Record<string, unknown>; evidence_ids: string[]; extractor_model: string; validation: { checks: Check[] } }[];
  rejected: { draft: { kind: string }; report: { rejected_reasons: string[] } }[];
  n_leaks: number;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${url}`);
  return (await r.json()) as T;
}

export const api = {
  runs: () => get<RunInfo[]>("/api/runs"),
  investigations: () => get<InvestigationSummary[]>("/api/investigations"),
  investigation: (id: string) => get<InvestigationDetail>(`/api/investigations/${id}`),
  pool: (run: string, night: string) => get<PoolNight>(`/api/runs/${run}/nights/${night}/candidates`),
  candidate: (run: string, night: string, oid: string) =>
    get<{ t_mjd: number; night_id: string; candidate: CandidateState }>(`/api/runs/${run}/nights/${night}/candidates/${oid}`),
  theaterNights: () => get<TheaterNightRef[]>("/theater/nights"),
  frames: (run: string, night: string) => get<TheaterData>(`/theater/${run}/${night}/frames`),
};
