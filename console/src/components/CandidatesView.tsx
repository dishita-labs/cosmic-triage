import { useEffect, useMemo, useState } from "react";
import type { CandidateState, PhotometryPoint } from "../types/contracts";
import { api, type PoolNight, type RunInfo } from "../lib/api";
import { fmtDate, fmtDateTime } from "../lib/time";
import LightCurve from "./LightCurve";

interface Props {
  runs: RunInfo[];
  run: string | null;
  night: string | null;
  oid: string | null;
  onChange: (run: string, night: string, oid: string | null) => void;
}

type SortKey = "oid" | "first_detection_mjd" | "n_detections" | "brightest_mag" | "latest_mag" | "fink_snn_snia_vs_nonia";

export default function CandidatesView({ runs, run, night, oid, onChange }: Props) {
  const [pool, setPool] = useState<PoolNight | null>(null);
  const [cand, setCand] = useState<{ t: number; c: CandidateState } | null>(null);
  const [cursor, setCursor] = useState(0);
  const [sort, setSort] = useState<{ k: SortKey; asc: boolean }>({ k: "latest_mag", asc: true });
  const runInfo = runs.find((r) => r.run_id === run) ?? null;

  useEffect(() => {
    if (!run || !night) return;
    api.pool(run, night).then(setPool).catch(() => setPool(null));
  }, [run, night]);

  useEffect(() => {
    if (!run || !night || !oid) return setCand(null);
    api.candidate(run, night, oid).then((r) => {
      setCand({ t: r.t_mjd, c: r.candidate });
      setCursor(r.t_mjd);
    }).catch(() => setCand(null));
  }, [run, night, oid]);

  const rows = useMemo(() => {
    const list = [...(pool?.candidates ?? [])];
    list.sort((a, b) => {
      const va = a[sort.k] ?? (sort.asc ? Infinity : -Infinity);
      const vb = b[sort.k] ?? (sort.asc ? Infinity : -Infinity);
      return (va < vb ? -1 : va > vb ? 1 : 0) * (sort.asc ? 1 : -1);
    });
    return list;
  }, [pool, sort]);

  const pts = (cand?.c.photometry ?? []) as PhotometryPoint[];
  const tMin = pts.length ? Math.min(...pts.map((p) => p.mjd)) : 0;
  const head = (k: SortKey, label: string) => (
    <th onClick={() => setSort((s) => ({ k, asc: s.k === k ? !s.asc : true }))} className={sort.k === k ? "sorted" : ""}>
      {label}{sort.k === k ? (sort.asc ? " ▲" : " ▼") : ""}
    </th>
  );

  return (
    <div className="cands">
      <div className="cands-bar">
        <label>Run
          <select value={run ?? ""} onChange={(e) => {
            const r = runs.find((x) => x.run_id === e.target.value);
            if (r) onChange(r.run_id, r.nights[0], null);
          }}>
            {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
          </select>
        </label>
        <label>Night (decision time t)
          <select value={night ?? ""} onChange={(e) => run && onChange(run, e.target.value, null)}>
            {(runInfo?.nights ?? []).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        {pool && <span className="muted">t = MJD {pool.t_mjd.toFixed(4)} ({fmtDateTime(pool.t_mjd)} UTC) · {pool.candidates.length} pool candidates · all values ≤ t</span>}
        {runInfo && <span className="prov">{runInfo.mode} · config <code>{runInfo.config_hash}</code> · output <code>{runInfo.output_hash.slice(0, 12)}</code></span>}
      </div>
      <div className="cands-main">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {head("oid", "Object")}
                {head("first_detection_mjd", "First det.")}
                {head("n_detections", "N det")}
                {head("brightest_mag", "Brightest")}
                {head("latest_mag", "Latest")}
                {head("fink_snn_snia_vs_nonia", "Fink SNN Ia")}
                <th>SIMBAD</th>
                <th>TNS @ alert</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.oid} className={c.oid === oid ? "on" : ""} onClick={() => run && night && onChange(run, night, c.oid)}>
                  <td className="mono">{c.oid}</td>
                  <td>{fmtDate(c.first_detection_mjd)}</td>
                  <td>{c.n_detections}</td>
                  <td>{c.brightest_mag.toFixed(2)}</td>
                  <td>{c.latest_mag.toFixed(2)} {c.latest_band}</td>
                  <td>{c.fink_snn_snia_vs_nonia?.toFixed(2) ?? "—"}</td>
                  <td>{c.fink_cdsxmatch ?? "—"}</td>
                  <td>{c.fink_tns_alert_time || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="lc-panel">
          {cand ? (
            <>
              <div className="lc-head">
                <h2 className="mono">{cand.c.oid}</h2>
                <span className="badge l0">L0 real photometry</span>
                <span className="muted">RA {cand.c.context.ra.toFixed(5)}° · Dec {cand.c.context.dec.toFixed(5)}° · b {cand.c.context.gal_b.toFixed(1)}°</span>
              </div>
              <LightCurve points={pts} tSnapshot={cand.t} cursor={cursor} />
              <div className="cursor-row">
                <span>Time cursor</span>
                <input type="range" min={tMin} max={cand.t} step={0.01} value={cursor}
                  onChange={(e) => setCursor(Number(e.target.value))} aria-label="Light-curve time cursor" />
                <span className="mono">{fmtDateTime(cursor)} UTC</span>
                <button className="ghost" onClick={() => setCursor(cand.t)}>to t</button>
              </div>
              <p className="muted small">
                Detections (circles) and non-detections (▽, 5σ limits) are those known at the decision time t; the cursor
                replays how the light curve grew. Class bands and beliefs arrive with M3.
              </p>
            </>
          ) : (
            <div className="empty">Select a candidate to see its light curve.</div>
          )}
        </div>
      </div>
    </div>
  );
}
