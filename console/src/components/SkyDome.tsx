import { useMemo } from "react";
import type { NightFrame } from "../types/contracts";
import type { PoolCandidate } from "../lib/api";
import { DOME, type Interp, project, skyColor, type XY } from "../lib/frames";
import { fmtTime } from "../lib/time";

interface Props {
  frames: NightFrame[];
  now: Interp;
  pool: Map<string, PoolCandidate>;
  minAlt: number;
  selected: string | null;
  hovered: string | null;
  showLabels: boolean;
  timeZone: string;
  onSelect: (oid: string | null) => void;
  onHover: (oid: string | null) => void;
}

const { size, cx, cy, r } = DOME;

/** Marker radius from the latest real magnitude (<= t): brighter -> larger. Presentation only. */
export function markerRadius(mag: number | undefined): number {
  if (mag === undefined) return 5;
  return Math.max(4, Math.min(14, 5 + (19.2 - mag) * 2.6));
}

function trackSegments(frames: NightFrame[], k: number): XY[][] {
  const segs: XY[][] = [];
  let cur: XY[] = [];
  for (const fr of frames) {
    const c = fr.candidates[k];
    if (c && c.alt >= 0) cur.push(project(c.alt, c.az));
    else if (cur.length) {
      segs.push(cur);
      cur = [];
    }
  }
  if (cur.length) segs.push(cur);
  return segs;
}

const path = (pts: XY[]) => pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join("");

function MoonGlyph({ at, phase, towards, rad }: { at: XY; phase: number; towards: XY; rad: number }) {
  // Lit limb faces the Sun's projected direction; illuminated fraction comes from astropy (backend).
  const ang = (Math.atan2(towards.y - at.y, towards.x - at.x) * 180) / Math.PI;
  const k = Math.max(0, Math.min(1, phase));
  const rx = Math.abs(1 - 2 * k) * rad;
  const lit = `M0,${-rad} A${rad},${rad} 0 0 1 0,${rad} A${rx},${rad} 0 0 ${k > 0.5 ? 1 : 0} 0,${-rad} Z`;
  return (
    <g transform={`translate(${at.x},${at.y}) rotate(${ang})`}>
      <circle r={rad * 2.6} fill="url(#moonHalo)" opacity={0.35 + 0.5 * k} />
      <circle r={rad} fill="#2a2f3d" />
      <path d={lit} fill="#f4f1e6" />
      <circle r={rad} fill="none" stroke="#fffbe8" strokeOpacity={0.35} strokeWidth={0.8} />
    </g>
  );
}

export default function SkyDome(p: Props) {
  const { frames, now, pool, minAlt, selected, hovered } = p;
  const oids = useMemo(() => frames[0]?.candidates.map((c) => c.oid) ?? [], [frames]);
  const tracks = useMemo(() => oids.map((_, k) => trackSegments(frames, k)), [frames, oids]);
  const hourTicks = useMemo(() => {
    // Hour marks along a track (selected candidate); frame times are on the 5-min grid.
    const out: { k: number; xy: XY; label: string }[] = [];
    if (!selected) return out;
    const k = oids.indexOf(selected);
    if (k < 0) return out;
    frames.forEach((fr) => {
      const m = Math.round((fr.t_mjd * 1440) % 60);
      const c = fr.candidates[k];
      if ((m === 0 || m === 60) && c.alt >= 0) out.push({ k, xy: project(c.alt, c.az), label: fmtTime(fr.t_mjd, p.timeZone) });
    });
    return out;
  }, [frames, oids, selected, p.timeZone]);

  const sky = skyColor(now.sunAlt);
  const sunRim = project(Math.max(now.sunAlt, 0), now.sunAz, r);
  const sunUp = now.sunAlt > -0.833;
  const glow = Math.max(0, Math.min(1, (now.sunAlt + 18) / 18));
  const moonUp = now.moonAlt > 0;
  const moonXY = project(Math.max(now.moonAlt, 0), now.moonAz);
  const minAltR = (r * (90 - minAlt)) / 90;

  return (
    <svg className="dome" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Alt-azimuth sky dome"
      onClick={() => p.onSelect(null)}>
      <defs>
        <radialGradient id="skyGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={sky} />
          <stop offset="85%" stopColor={sky} />
          <stop offset="100%" stopColor="#000" stopOpacity={0.9} />
        </radialGradient>
        <radialGradient id="sunGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffb36b" stopOpacity={0.85} />
          <stop offset="45%" stopColor="#ff7a45" stopOpacity={0.25} />
          <stop offset="100%" stopColor="#ff7a45" stopOpacity={0} />
        </radialGradient>
        <radialGradient id="moonHalo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fdf6d8" stopOpacity={0.6} />
          <stop offset="100%" stopColor="#fdf6d8" stopOpacity={0} />
        </radialGradient>
        <clipPath id="domeClip">
          <circle cx={cx} cy={cy} r={r} />
        </clipPath>
        <filter id="soft" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.2" />
        </filter>
      </defs>

      <circle cx={cx} cy={cy} r={r + 40} fill="#02040a" />
      <g clipPath="url(#domeClip)">
        <circle cx={cx} cy={cy} r={r} fill="url(#skyGrad)" />
        {glow > 0 && (
          <circle cx={sunRim.x} cy={sunRim.y} r={r * (0.55 + 0.45 * glow)} fill="url(#sunGlow)" opacity={glow} />
        )}
        {/* altitude rings */}
        {[30, 60].map((a) => (
          <circle key={a} cx={cx} cy={cy} r={(r * (90 - a)) / 90} className="ring" />
        ))}
        {[0, 45, 90, 135].map((az) => {
          const a = project(0, az);
          const b = project(0, az + 180);
          return <line key={az} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="meridian" />;
        })}
        {/* facility altitude limit (config) */}
        <circle cx={cx} cy={cy} r={minAltR} className="limit-ring" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#000" strokeOpacity={0.35} strokeWidth={(r - minAltR) * 2}
          className="below-limit" />

        {/* altitude tracks (real geometry from astropy frames) */}
        {tracks.map((segs, k) => {
          const oid = oids[k];
          const on = oid === selected || oid === hovered;
          return segs.map((s, j) => (
            <path key={`${oid}-${j}`} d={path(s)} className={on ? "track track-on" : "track"} />
          ));
        })}
        {hourTicks.map((h, i) => (
          <g key={i} transform={`translate(${h.xy.x},${h.xy.y})`}>
            <circle r={2.6} className="tick" />
            <text x={7} y={4} className="tick-label">{h.label}</text>
          </g>
        ))}

        {/* Sun (only drawn above the horizon) */}
        {sunUp && (
          <g transform={`translate(${project(now.sunAlt, now.sunAz).x},${project(now.sunAlt, now.sunAz).y})`}>
            <circle r={34} fill="url(#sunGlow)" />
            <circle r={13} fill="#ffe7a8" />
          </g>
        )}
        {moonUp && <MoonGlyph at={moonXY} phase={now.moonPhase} towards={sunRim} rad={13} />}

        {/* candidates: real (L0), solid */}
        {oids.map((oid) => {
          const c = now.cand.get(oid);
          if (!c || c.alt < 0) return null;
          const pc = pool.get(oid);
          const rad = markerRadius(pc?.latest_mag);
          const observable = c.alt >= minAlt;
          const isSel = oid === selected;
          const isHov = oid === hovered;
          return (
            <g key={oid} transform={`translate(${c.xy.x},${c.xy.y})`} className="cand"
              onClick={(e) => { e.stopPropagation(); p.onSelect(isSel ? null : oid); }}
              onMouseEnter={() => p.onHover(oid)} onMouseLeave={() => p.onHover(null)}>
              <circle r={rad * 2.2} className={observable ? "cand-halo" : "cand-halo dim"} filter="url(#soft)" />
              <circle r={rad} className={observable ? "cand-dot" : "cand-dot dim"} />
              {(isSel || isHov) && <circle r={rad + 7} className="cand-ring" />}
              {(p.showLabels || isSel || isHov) && (
                <text x={rad + 8} y={-rad - 2} className={isSel ? "cand-label sel" : "cand-label"}>
                  {oid}
                  {pc ? ` · ${pc.latest_mag.toFixed(1)}${pc.latest_band}` : ""}
                </text>
              )}
            </g>
          );
        })}
      </g>

      {/* horizon + cardinal points (dome seen from below: N up, E left) */}
      <circle cx={cx} cy={cy} r={r} className="horizon" />
      {[["N", 0], ["E", 90], ["S", 180], ["W", 270]].map(([l, az]) => {
        const pnt = project(-9, az as number);
        return <text key={l as string} x={pnt.x} y={pnt.y + 9} className="cardinal">{l}</text>;
      })}
      {[30, 60].filter((a) => a !== minAlt).map((a) => (
        <text key={a} x={cx + 6} y={cy - (r * (90 - a)) / 90 - 6} className="ring-label">{a}°</text>
      ))}
      <text x={cx + 6} y={cy - minAltR - 6} className="limit-label">{minAlt}° · facility limit</text>
      {!sunUp && now.sunAlt > -18 && (
        <text x={sunRim.x} y={sunRim.y} className="sun-below" textAnchor="middle"
          transform={`translate(${(sunRim.x - cx) * 0.08},${(sunRim.y - cy) * 0.08})`}>
          ☉ {now.sunAlt.toFixed(0)}°
        </text>
      )}
    </svg>
  );
}
