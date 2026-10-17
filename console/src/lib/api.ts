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

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${url}`);
  return (await r.json()) as T;
}

export const api = {
  runs: () => get<RunInfo[]>("/api/runs"),
  pool: (run: string, night: string) => get<PoolNight>(`/api/runs/${run}/nights/${night}/candidates`),
  candidate: (run: string, night: string, oid: string) =>
    get<{ t_mjd: number; night_id: string; candidate: CandidateState }>(`/api/runs/${run}/nights/${night}/candidates/${oid}`),
  theaterNights: () => get<TheaterNightRef[]>("/theater/nights"),
  frames: (run: string, night: string) => get<TheaterData>(`/theater/${run}/${night}/frames`),
};
