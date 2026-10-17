import { useCallback, useMemo, useRef } from "react";
import type { NightFrame, TheaterNight } from "../types/contracts";
import { TWILIGHT_COLORS } from "../lib/frames";
import { fmtTime } from "../lib/time";

interface Props {
  header: TheaterNight;
  frames: NightFrame[];
  t: number;
  timeZone: string;
  onSeek: (t: number) => void;
}

/** Time cursor over the night, with twilight bands from the backend frames. */
export default function Scrubber({ header, frames, t, timeZone, onSeek }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const span = header.end_mjd - header.start_mjd;
  const pct = (m: number) => `${(((m - header.start_mjd) / span) * 100).toFixed(3)}%`;
  const bands = useMemo(() => {
    const out: { from: number; to: number; tw: NightFrame["twilight"] }[] = [];
    frames.forEach((f, i) => {
      const to = frames[i + 1]?.t_mjd ?? f.t_mjd;
      const last = out[out.length - 1];
      if (last && last.tw === f.twilight) last.to = to;
      else out.push({ from: f.t_mjd, to, tw: f.twilight });
    });
    return out;
  }, [frames]);
  const hours = useMemo(() => frames.filter((f) => Math.round((f.t_mjd * 1440) % 60) % 60 === 0), [frames]);
  const seekAt = useCallback(
    (clientX: number) => {
      const el = ref.current;
      if (!el) return;
      const b = el.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (clientX - b.left) / b.width));
      onSeek(header.start_mjd + f * span);
    },
    [header.start_mjd, span, onSeek],
  );
  const marks: [string, number][] = [
    ["sunset", header.sunset_mjd],
    ["astro dusk", header.astro_dusk_mjd],
    ["astro dawn", header.astro_dawn_mjd],
    ["sunrise", header.sunrise_mjd],
  ];
  return (
    <div className="scrubber">
      <div
        className="scrub-track"
        ref={ref}
        onPointerDown={(e) => {
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          seekAt(e.clientX);
        }}
        onPointerMove={(e) => e.buttons === 1 && seekAt(e.clientX)}
        role="slider"
        aria-valuemin={header.start_mjd}
        aria-valuemax={header.end_mjd}
        aria-valuenow={t}
        aria-label="Time cursor"
      >
        {bands.map((b, i) => (
          <div key={i} className="band" style={{ left: pct(b.from), width: `calc(${pct(b.to)} - ${pct(b.from)})`, background: TWILIGHT_COLORS[b.tw] }} />
        ))}
        {hours.map((h) => (
          <div key={h.t_mjd} className="hour" style={{ left: pct(h.t_mjd) }}>
            <span>{fmtTime(h.t_mjd, timeZone).slice(0, 2)}</span>
          </div>
        ))}
        {marks.map(([l, m]) => (
          <div key={l} className="mark" style={{ left: pct(m) }} title={`${l} ${fmtTime(m, timeZone)}`}>
            <span>{l}</span>
          </div>
        ))}
        <div className="cursor" style={{ left: pct(t) }} />
      </div>
    </div>
  );
}
