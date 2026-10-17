import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CandidateState } from "../types/contracts";
import { api, type PoolCandidate, type TheaterData, type TheaterNightRef } from "../lib/api";
import { interpolate } from "../lib/frames";
import { fmtDate, fmtTime, tzAbbrev } from "../lib/time";
import SkyDome from "./SkyDome";
import Scrubber from "./Scrubber";
import LightCurve from "./LightCurve";

interface Props {
  nights: TheaterNightRef[];
  current: TheaterNightRef | null;
  onPick: (n: TheaterNightRef) => void;
  onOpenCandidate: (oid: string) => void;
}

const SPEEDS = [2, 5, 15, 30, 60]; // simulated minutes per real second

export default function TheaterView({ nights, current, onPick, onOpenCandidate }: Props) {
  const [data, setData] = useState<TheaterData | null>(null);
  const [pool, setPool] = useState<Map<string, PoolCandidate>>(new Map());
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(15);
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [labels, setLabels] = useState(false);
  const [detail, setDetail] = useState<{ t: number; c: CandidateState } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const shellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!current) return;
    let live = true;
    setErr(null);
    Promise.all([api.frames(current.run_id, current.night), api.pool(current.run_id, current.night)])
      .then(([d, p]) => {
        if (!live) return;
        setData(d);
        setPool(new Map(p.candidates.map((c) => [c.oid, c])));
        setT(d.header.astro_dusk_mjd);
        setSelected(null);
      })
      .catch((e) => live && setErr(String(e)));
    return () => {
      live = false;
    };
  }, [current]);

  useEffect(() => {
    if (!selected || !current) return setDetail(null);
    api.candidate(current.run_id, current.night, selected).then((r) => setDetail({ t: r.t_mjd, c: r.candidate })).catch(() => setDetail(null));
  }, [selected, current]);

  // Playback loop: advance the cursor at `speed` simulated minutes per second.
  useEffect(() => {
    if (!playing || !data) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setT((prev) => {
        const next = prev + (dt * speed) / 1440;
        if (next >= data.header.end_mjd) {
          setPlaying(false);
          return data.header.end_mjd;
        }
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, data]);

  const fullscreen = useCallback(() => {
    const el = shellRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!data || (e.target as HTMLElement)?.tagName === "SELECT") return;
      const step = (e.shiftKey ? 60 : 5) / 1440;
      const clamp = (v: number) => Math.max(data.header.start_mjd, Math.min(data.header.end_mjd, v));
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
      else if (e.key === "ArrowRight") setT((v) => clamp(v + step));
      else if (e.key === "ArrowLeft") setT((v) => clamp(v - step));
      else if (e.key === "Home") setT(data.header.start_mjd);
      else if (e.key === "End") setT(data.header.end_mjd);
      else if (e.key.toLowerCase() === "f") fullscreen();
      else if (e.key.toLowerCase() === "l") setLabels((v) => !v);
      else if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [data, fullscreen]);

  const now = useMemo(() => (data ? interpolate(data.frames, t) : null), [data, t]);
  const tz = data?.header.site_timezone ?? "UTC";
  const minAlt = data?.header.min_altitude_deg ?? 30;

  const visible = useMemo(() => {
    if (!now) return [];
    return [...now.cand.entries()]
      .filter(([, c]) => c.alt > 0)
      .sort((a, b) => b[1].alt - a[1].alt)
      .map(([oid, c]) => ({ oid, alt: c.alt, pc: pool.get(oid) }));
  }, [now, pool]);
  const nObservable = visible.filter((v) => v.alt >= minAlt).length;

  if (err) return <div className="empty">Could not load the night: {err}. Is the API running (uv run uvicorn cosmic_triage.api.app:app)?</div>;
  if (!current || !data || !now) return <div className="empty">{nights.length ? "Loading night…" : "No Theater nights yet. Run scripts/run_m1_spine.py."}</div>;
  const h = data.header;
  const sel = selected ? pool.get(selected) : null;
  const selAlt = selected ? now.cand.get(selected)?.alt : undefined;

  return (
    <div className="theater" ref={shellRef}>
      {h.mode === "exploratory" && <div className="watermark">EXPLORATORY</div>}
      <header className="th-top">
        <div className="th-title">
          <span className="eyebrow">Night Theater · S0</span>
          <h1>
            Night of {h.night_id} <span className="muted">· {h.site_name}</span>
          </h1>
        </div>
        <div className="th-clock">
          <div className="clock-big">{fmtTime(t, tz)} <small>{tzAbbrev(t, tz)}</small></div>
          <div className="clock-sub">{fmtDate(t, "UTC")} {fmtTime(t, "UTC")} UTC · <span className={`tw tw-${now.twilight}`}>{now.twilight === "astro" ? "astronomical twilight" : now.twilight === "night" ? "dark night" : `${now.twilight}${now.twilight === "day" ? "" : " twilight"}`}</span></div>
        </div>
        <div className="th-pick">
          <select value={`${current.run_id}|${current.night}`} onChange={(e) => {
            const [r, n] = e.target.value.split("|");
            const pick = nights.find((x) => x.run_id === r && x.night === n);
            if (pick) onPick(pick);
          }} aria-label="Night">
            {nights.map((n) => (
              <option key={`${n.run_id}|${n.night}`} value={`${n.run_id}|${n.night}`}>{n.night} · {n.n_candidates} candidates</option>
            ))}
          </select>
        </div>
      </header>

      <div className="th-main">
        <div className="dome-wrap">
          <SkyDome frames={data.frames} now={now} pool={pool} minAlt={minAlt} selected={selected} hovered={hovered}
            showLabels={labels} timeZone={tz} onSelect={setSelected} onHover={setHovered} />
        </div>

        <aside className="th-side">
          <section className="card stats">
            <div><span className="k">Sun</span><span className="v">{now.sunAlt.toFixed(1)}°</span></div>
            <div><span className="k">Moon</span><span className="v">{now.moonAlt.toFixed(1)}° · {(now.moonPhase * 100).toFixed(0)}% lit</span></div>
            <div><span className="k">Above {minAlt}°</span><span className="v">{nObservable} / {h.n_candidates}</span></div>
            <div><span className="k">Dark window</span><span className="v">{fmtTime(h.astro_dusk_mjd, tz)}–{fmtTime(h.astro_dawn_mjd, tz)}</span></div>
          </section>

          {sel ? (
            <section className="card selected">
              <div className="sel-head">
                <div>
                  <span className="eyebrow">Selected candidate · real (L0)</span>
                  <h2>{sel.oid}</h2>
                </div>
                <button className="ghost" onClick={() => setSelected(null)} aria-label="Close">✕</button>
              </div>
              <dl>
                <dt>Altitude now</dt><dd>{selAlt !== undefined ? `${selAlt.toFixed(1)}°` : "—"}</dd>
                <dt>Latest</dt><dd>{sel.latest_mag.toFixed(2)} {sel.latest_band}</dd>
                <dt>Brightest ≤ t</dt><dd>{sel.brightest_mag.toFixed(2)}</dd>
                <dt>Detections ≤ t</dt><dd>{sel.n_detections} <span className="muted">(+{sel.n_nondetections} limits)</span></dd>
                <dt>First detected</dt><dd>{fmtDate(sel.first_detection_mjd)}</dd>
                <dt>Fink SNN Ia (alert-time)</dt><dd>{sel.fink_snn_snia_vs_nonia?.toFixed(2) ?? "—"}</dd>
                <dt>SIMBAD xmatch</dt><dd>{sel.fink_cdsxmatch ?? "—"}</dd>
                <dt>TNS at alert time</dt><dd>{sel.fink_tns_alert_time || "—"}</dd>
                <dt>Belief / reward</dt><dd className="muted">not computed until M3</dd>
              </dl>
              {detail && <LightCurve points={detail.c.photometry as never} tSnapshot={detail.t} cursor={detail.t} compact />}
              <button className="primary" onClick={() => onOpenCandidate(sel.oid)}>Open light curve explorer →</button>
            </section>
          ) : (
            <section className="card list">
              <span className="eyebrow">Above the horizon now · by altitude</span>
              <ul>
                {visible.slice(0, 14).map((v) => (
                  <li key={v.oid} className={v.alt >= minAlt ? "" : "dim"} onMouseEnter={() => setHovered(v.oid)}
                    onMouseLeave={() => setHovered(null)} onClick={() => setSelected(v.oid)}>
                    <span className="oid">{v.oid}</span>
                    <span className="alt">{v.alt.toFixed(0)}°</span>
                    <span className="mag">{v.pc ? `${v.pc.latest_mag.toFixed(1)}${v.pc.latest_band}` : ""}</span>
                  </li>
                ))}
                {visible.length > 14 && <li className="more">+{visible.length - 14} more</li>}
                {!visible.length && <li className="more">No pool candidates above the horizon.</li>}
              </ul>
            </section>
          )}

          <section className="card legend">
            <p className="truth">Telescope and its observations are simulated; sky, candidates, detections, and reports are real.</p>
            <div className="lg-row"><span className="sw sw-real" /> Candidate (real ZTF, ≤ t) · <span className="badge l0">L0</span></div>
            <div className="lg-row"><span className="sw sw-dim" /> Below the {minAlt}° facility limit</div>
            <div className="lg-row"><span className="sw sw-sim" /> Simulated facility · idle until S1 · <span className="badge l1">L1</span></div>
            <div className="lg-row muted">Marker size: latest real magnitude. Positions: astropy, 5-min frames.</div>
          </section>
        </aside>
      </div>

      <footer className="th-bottom">
        <div className="controls">
          <button className="play" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause" : "Play"}>{playing ? "❚❚" : "▶"}</button>
          <div className="speed" role="group" aria-label="Speed">
            {SPEEDS.map((s) => (
              <button key={s} className={s === speed ? "on" : ""} onClick={() => setSpeed(s)}>{s}m/s</button>
            ))}
          </div>
          <button className="ghost" onClick={() => setLabels((v) => !v)}>{labels ? "Hide" : "Show"} labels</button>
          <button className="ghost" onClick={fullscreen}>Full screen</button>
        </div>
        <Scrubber header={h} frames={data.frames} t={t} timeZone={tz} onSeek={setT} />
        <div className="provenance">
          {h.mode === "bench" ? <>run <code>{h.run_id}</code> · config <code>{h.config_hash}</code></> : <>EXPLORATORY run <code>{h.run_id}</code></>}
          <span className="keys">space play · ←/→ 5 min · shift 1 h · F full screen · L labels</span>
        </div>
      </footer>
    </div>
  );
}
