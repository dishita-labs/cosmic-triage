import { useEffect, useState } from "react";
import { api, type RunInfo, type TheaterNightRef } from "./lib/api";
import TheaterView from "./components/TheaterView";
import CandidatesView from "./components/CandidatesView";
import InvestigationsView from "./components/InvestigationsView";

type Tab = "theater" | "candidates" | "investigations";

export default function App() {
  // Hash routing (#theater, #candidates, #candidates/<oid>) so views are linkable.
  const initial = window.location.hash.replace(/^#/, "").split("/");
  const [tab, setTab] = useState<Tab>(initial[0] === "candidates" || initial[0] === "investigations" ? initial[0] : "theater");
  const [inv, setInv] = useState<string | null>(initial[0] === "investigations" ? initial[1] || null : null);
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [nights, setNights] = useState<TheaterNightRef[]>([]);
  const [current, setCurrent] = useState<TheaterNightRef | null>(null);
  const [sel, setSel] = useState<{ run: string | null; night: string | null; oid: string | null }>({ run: null, night: null, oid: null });
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.runs(), api.theaterNights()])
      .then(([r, n]) => {
        setRuns(r);
        setNights(n);
        if (n.length) setCurrent(n[0]);
        if (r.length) setSel({ run: r[0].run_id, night: r[0].nights[0] ?? null, oid: initial[1] || null });
      })
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    const h = tab === "candidates" && sel.oid ? `#candidates/${sel.oid}` : tab === "investigations" && inv ? `#investigations/${inv}` : `#${tab}`;
    if (window.location.hash !== h) window.history.replaceState(null, "", h);
  }, [tab, sel.oid, inv]);

  return (
    <div className={`app tab-${tab}`}>
      <nav className="topnav">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden><circle cx="16" cy="16" r="13" fill="none" stroke="#7fd4ff" strokeWidth="2" /><circle cx="21" cy="11" r="2.6" fill="#ffe8a3" /></svg>
          Cosmic Triage <span className="muted">Observatory Console v0</span>
        </div>
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "theater"} className={tab === "theater" ? "on" : ""} onClick={() => setTab("theater")}>Night Theater</button>
          <button role="tab" aria-selected={tab === "candidates"} className={tab === "candidates" ? "on" : ""} onClick={() => setTab("candidates")}>Candidates</button>
          <button role="tab" aria-selected={tab === "investigations"} className={tab === "investigations" ? "on" : ""} onClick={() => setTab("investigations")}>Investigations</button>
        </div>
      </nav>
      {err && <div className="empty">API unreachable ({err}). Start it with <code>uv run uvicorn cosmic_triage.api.app:app</code>.</div>}
      {!err && tab === "theater" && (
        <TheaterView nights={nights} current={current} onPick={setCurrent} onOpenCandidate={(oid) => {
          if (current) setSel({ run: current.run_id, night: current.night, oid });
          setTab("candidates");
        }} />
      )}
      {!err && tab === "investigations" && <InvestigationsView runId={inv} onPick={setInv} />}
      {!err && tab === "candidates" && (
        <CandidatesView runs={runs} run={sel.run} night={sel.night} oid={sel.oid}
          onChange={(run, night, oid) => setSel({ run, night, oid })} />
      )}
    </div>
  );
}
