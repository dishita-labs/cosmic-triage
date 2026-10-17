import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { PhotometryPoint } from "../types/contracts";

interface Props {
  points: PhotometryPoint[];
  tSnapshot: number;
  cursor: number;
  compact?: boolean;
}

const BAND_COLOR: Record<string, string> = { g: "#4fd18b", r: "#ff6b6b", i: "#ffc75a" };

/** Light curve with upper limits; points after the cursor are not drawn. All points are real (L0, <= t). */
export default function LightCurve({ points, tSnapshot, cursor, compact }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const vis = points.filter((p) => p.mjd <= cursor);
    const traces: Partial<Plotly.PlotData>[] = [];
    for (const band of ["g", "r", "i"]) {
      const det = vis.filter((p) => p.band === band && p.is_detection);
      const ul = vis.filter((p) => p.band === band && !p.is_detection);
      if (det.length)
        traces.push({
          x: det.map((p) => p.mjd), y: det.map((p) => p.mag as number), mode: "markers", type: "scatter",
          name: `${band} detection`, marker: { color: BAND_COLOR[band], size: compact ? 6 : 9, line: { width: 1, color: "#0b1020" } },
          error_y: { type: "data", array: det.map((p) => p.mag_err ?? 0), visible: true, color: BAND_COLOR[band], thickness: 1.2 },
          hovertemplate: `${band}  %{y:.2f} mag<br>MJD %{x:.4f}<extra></extra>`,
        });
      if (ul.length)
        traces.push({
          x: ul.map((p) => p.mjd), y: ul.map((p) => p.limiting_mag as number), mode: "markers", type: "scatter",
          name: `${band} upper limit`, marker: { color: BAND_COLOR[band], symbol: "triangle-down", size: compact ? 6 : 9, opacity: 0.38 },
          hovertemplate: `${band} non-detection  > %{y:.2f}<br>MJD %{x:.4f}<extra></extra>`,
        });
    }
    const xs = points.map((p) => p.mjd);
    const lo = Math.min(...xs, cursor) - 1;
    const hi = Math.max(tSnapshot, cursor) + 0.5;
    Plotly.react(
      ref.current,
      traces as Plotly.Data[],
      {
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(255,255,255,0.02)",
        font: { color: "#cdd8ee", family: "Inter, system-ui, sans-serif", size: compact ? 10 : 13 },
        margin: compact ? { l: 36, r: 8, t: 6, b: 26 } : { l: 56, r: 18, t: 16, b: 48 },
        showlegend: !compact, legend: { orientation: "h", y: -0.18 },
        xaxis: { title: compact ? undefined : { text: "MJD" }, tickformat: "d", range: [lo, hi], gridcolor: "rgba(255,255,255,0.06)", zeroline: false },
        yaxis: { title: compact ? undefined : { text: "AB magnitude" }, autorange: "reversed", gridcolor: "rgba(255,255,255,0.06)", zeroline: false },
        shapes: [
          { type: "line", x0: tSnapshot, x1: tSnapshot, yref: "paper", y0: 0, y1: 1, line: { color: "#ffb347", width: 1.5 } },
          { type: "line", x0: cursor, x1: cursor, yref: "paper", y0: 0, y1: 1, line: { color: "#e8f1ff", width: 1, dash: "dot" } },
        ],
        annotations: compact ? [] : [
          { x: tSnapshot, yref: "paper", y: 1, text: "t (decision time)", showarrow: false, font: { color: "#ffb347", size: 11 }, xanchor: "left", yanchor: "top" },
        ],
      },
      { displayModeBar: false, responsive: true },
    );
  }, [points, tSnapshot, cursor, compact]);
  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) Plotly.purge(el);
    };
  }, []);
  return <div ref={ref} className={compact ? "lc lc-compact" : "lc"} />;
}
