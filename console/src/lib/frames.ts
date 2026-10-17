// Frame interpolation for smooth playback. Positions come from backend NightFrames (astropy);
// the player projects alt/az to the dome and linearly interpolates between 5-minute frames.
import type { NightFrame } from "../types/contracts";

export interface XY {
  x: number;
  y: number;
}

export const DOME = { size: 1000, cx: 500, cy: 500, r: 440 };

/** Zenith-centred dome as seen looking up: north at top, east on the left. */
export function project(alt: number, az: number, r = DOME.r): XY {
  const rho = (r * (90 - alt)) / 90;
  const a = (az * Math.PI) / 180;
  return { x: DOME.cx - rho * Math.sin(a), y: DOME.cy - rho * Math.cos(a) };
}

export function frameIndex(frames: NightFrame[], t: number): { i: number; f: number } {
  if (t <= frames[0].t_mjd) return { i: 0, f: 0 };
  const last = frames.length - 1;
  if (t >= frames[last].t_mjd) return { i: last, f: 0 };
  const step = frames[1].t_mjd - frames[0].t_mjd;
  const i = Math.min(last - 1, Math.floor((t - frames[0].t_mjd) / step));
  return { i, f: (t - frames[i].t_mjd) / step };
}

export const lerp = (a: number, b: number, f: number) => a + (b - a) * f;

export interface Interp {
  t: number;
  sunAlt: number;
  sunAz: number;
  moonAlt: number;
  moonAz: number;
  moonPhase: number;
  twilight: NightFrame["twilight"];
  frame: NightFrame;
  cand: Map<string, { alt: number; xy: XY }>;
}

function lerpAz(a: number, b: number, f: number): number {
  let d = b - a;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return (a + d * f + 360) % 360;
}

export function interpolate(frames: NightFrame[], t: number): Interp {
  const { i, f } = frameIndex(frames, t);
  const A = frames[i];
  const B = frames[Math.min(i + 1, frames.length - 1)];
  const cand = new Map<string, { alt: number; xy: XY }>();
  A.candidates.forEach((ca, k) => {
    const cb = B.candidates[k] ?? ca;
    const pa = project(ca.alt, ca.az);
    const pb = project(cb.alt, cb.az);
    cand.set(ca.oid, { alt: lerp(ca.alt, cb.alt, f), xy: { x: lerp(pa.x, pb.x, f), y: lerp(pa.y, pb.y, f) } });
  });
  return {
    t,
    sunAlt: lerp(A.sun_alt, B.sun_alt, f),
    sunAz: lerpAz(A.sun_az, B.sun_az, f),
    moonAlt: lerp(A.moon.alt, B.moon.alt, f),
    moonAz: lerpAz(A.moon.az, B.moon.az, f),
    moonPhase: lerp(A.moon.phase, B.moon.phase, f),
    twilight: f < 0.5 ? A.twilight : B.twilight,
    frame: f < 0.5 ? A : B,
    cand,
  };
}

/** Sky colour keyed on the backend's sun altitude (presentation only). */
const STOPS: [number, [number, number, number]][] = [
  [10, [58, 112, 176]],
  [0, [36, 74, 132]],
  [-6, [22, 40, 88]],
  [-12, [11, 20, 48]],
  [-18, [6, 10, 26]],
  [-90, [3, 6, 16]],
];

export function skyColor(sunAlt: number): string {
  for (let k = 0; k < STOPS.length - 1; k++) {
    const [a0, c0] = STOPS[k];
    const [a1, c1] = STOPS[k + 1];
    if (sunAlt <= a0 && sunAlt >= a1) {
      const f = (a0 - sunAlt) / (a0 - a1);
      const c = c0.map((v, j) => Math.round(lerp(v, c1[j], f)));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return sunAlt > STOPS[0][0] ? "rgb(58,112,176)" : "rgb(3,6,16)";
}

export const TWILIGHT_COLORS: Record<NightFrame["twilight"], string> = {
  day: "#3a70b0",
  civil: "#2a4c8a",
  nautical: "#17295a",
  astro: "#0d1838",
  night: "#060b1c",
};
