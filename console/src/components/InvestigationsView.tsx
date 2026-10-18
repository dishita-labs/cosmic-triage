import { useEffect, useMemo, useState } from "react";
import { api, type InvestigationDetail, type InvestigationSummary } from "../lib/api";

// Investigation trace + evidence ledger (ARCHITECTURE §8.1). Renders replay artifacts only; the API computes dt/leak.

const OUTCOME: Record<string, string> = { claims: "validated claims", no_context_found: "no context found", gated_out: "gated out" };

function rel(dt: number | null): string {
  if (dt === null) return "static";
  const s = dt <= 0 ? "−" : "+";
  return `t ${s} ${Math.abs(dt).toFixed(2)} d`;
}

function short(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toPrecision(6).replace(/\.?0+$/, "");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function InvestigationsView({ runId, onPick }: { runId: string | null; onPick: (id: string) => void }) {
  const [list, setList] = useState<InvestigationSummary[]>([]);
  const [d, setD] = useState<InvestigationDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.investigations().then((l) => {
      setList(l);
      if (!runId && l.length) onPick(l[0].run_id);
    }).catch((e) => setErr(String(e)));
  }, []);
  useEffect(() => {
    if (runId) api.investigation(runId).then(setD).catch((e) => setErr(String(e)));
  }, [runId]);

  const shown = useMemo(() => list.filter((r) => !filter || r.oid.includes(filter) || (r.label ?? "").includes(filter)), [list, filter]);
  if (err) return <div className="empty">{err}</div>;
  if (!list.length) return <div className="empty">No investigation traces yet. Run <code>uv run python scripts/demo_investigate.py &lt;OID&gt; &lt;MJD&gt;</code>.</div>;

  return (
    <div className="inv">
      <aside className="inv-list">
        <input placeholder="filter oid / label" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <ul>
          {shown.map((r) => (
            <li key={r.run_id} className={r.run_id === runId ? "on" : ""} onClick={() => onPick(r.run_id)}>
              <span className="oid">{r.oid}</span>
              <span className={`out out-${r.outcome}`}>{r.n_claims ? `${r.n_claims} claim${r.n_claims > 1 ? "s" : ""}` : OUTCOME[r.outcome]}</span>
              <span className="muted sm">{r.night_id}{r.label ? ` · ${r.label}` : ""}</span>
            </li>
          ))}
        </ul>
      </aside>
      {d && (
        <section className="inv-main">
          {d.header.mode === "exploratory" && <div className="watermark">EXPLORATORY</div>}
          <header className="inv-head card">
            <div>
              <span className="eyebrow">Investigation · {d.header.mode} · not a benchmark result</span>
              <h2>{d.header.oid} <span className="muted">at t = MJD {d.header.t_mjd.toFixed(4)} ({d.header.night_id})</span></h2>
              <div className="muted sm"><code>{d.header.run_id}</code> · config <code>{d.header.config_version}</code> · seed {d.header.seed} · output <code>{d.header.output_hash.slice(0, 12)}</code></div>
            </div>
            <div className="inv-kpis">
              <div><span className="k">Outcome</span><span className={`v out-${d.header.outcome}`}>{OUTCOME[d.header.outcome]}</span></div>
              <div><span className="k">Stop</span><span className="v">{d.header.stop_reason}</span></div>
              <div><span className="k">Tool calls</span><span className="v">{d.header.counters.tool_calls}</span></div>
              <div><span className="k">Cost</span><span className="v">${d.header.cost_usd.toFixed(4)}</span></div>
              <div><span className="k">Leakage</span><span className="v">{d.n_leaks ? <span className="leak">LEAK ×{d.n_leaks}</span> : <span className="noleak">none · all ≤ t</span>}</span></div>
            </div>
          </header>
          {d.header.effects && (
            <div className="card effects">
              <span className="eyebrow">ClaimEffects (code-owned)</span>
              spectrum reward factor <b>{short(d.header.effects.spectrum_reward_factor)}</b>
              {d.header.effects.log.map((e, i) => <span key={i} className={`chip ${e.status}`}>{e.claim_kind}: {e.status}{e.factor !== null ? ` ×${e.factor}` : ""}</span>)}
            </div>
          )}

          <div className="inv-grid">
            <div className="card">
              <span className="eyebrow">Trace · {d.spans.length} spans</span>
              <ol className="spans">
                {d.spans.map((s) => (
                  <li key={s.span_id} className={`span k-${s.kind} st-${s.status}`}>
                    <span className="sk">{s.kind}</span>
                    <span className="sn">{s.name}</span>
                    <span className="sm muted">
                      {s.status !== "ok" && <b className={`st st-${s.status}`}>{s.status} </b>}
                      {s.latency_ms !== null && `${s.latency_ms.toFixed(0)} ms`}
                      {s.cache_hit === true && " · cache"}{s.model_id && ` · ${s.model_id}`}{s.usd > 0 && ` · $${s.usd.toFixed(4)}`}
                    </span>
                    <div className="sa">
                      {s.kind === "gate" && <span>{short(s.attrs.reason)}</span>}
                      {s.kind === "tool" && s.status === "ok" && <span>{short(s.attrs.new_evidence)} new evidence{Number(s.attrs.filtered_post_t) ? ` · ${s.attrs.filtered_post_t} filtered (post-t)` : ""}</span>}
                      {s.kind === "tool" && s.status !== "ok" && <span>{s.error ?? short(s.attrs.reason)}</span>}
                      {s.kind === "extract" && <span>{short(s.attrs.n_drafts)} drafts {s.error ?? ""}</span>}
                      {s.kind === "validator" && <span className={s.attrs.accepted ? "ok" : "bad"}>{s.attrs.accepted ? "accepted" : "rejected"}{!s.attrs.accepted && ": " + (s.attrs.checks as { name: string; passed: boolean; detail: string }[]).filter((c) => !c.passed).map((c) => `${c.name} (${c.detail})`).join("; ")}</span>}
                      {s.kind === "plan" && <span>{short(s.attrs.outcome)} · {short(s.attrs.stop_reason)}</span>}
                      {s.kind === "model" && <span>{s.error ?? `noul ${short(s.attrs.noul)}`}</span>}
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            <div className="stack">
              <div className="card">
                <span className="eyebrow">Accepted claims · {d.claims.length}</span>
                {!d.claims.length && <p className="muted">None{d.header.outcome === "no_context_found" ? " — explicit no_context_found" : ""}.</p>}
                {d.claims.map((c, i) => (
                  <div key={i} className="claim">
                    <div><b>{c.kind}</b> <span className="muted sm">by {c.extractor_model}</span></div>
                    <div className="kv">{Object.entries(c.payload).map(([k, v]) => <span key={k}><i>{k}</i> {short(v)}</span>)}</div>
                    <div className="checks">{c.validation.checks.map((ch) => <span key={ch.name} className={ch.passed ? "ok" : "bad"} title={ch.detail}>{ch.passed ? "✓" : "✗"} {ch.name}</span>)}</div>
                    <div className="sm muted">cites {c.evidence_ids.join(", ")}</div>
                  </div>
                ))}
              </div>
              {d.rejected.length > 0 && (
                <div className="card">
                  <span className="eyebrow">Rejected drafts · {d.rejected.length}</span>
                  {d.rejected.map((r, i) => (
                    <div key={i} className="claim rej"><b>{r.draft.kind}</b> <span className="sm">{r.report.rejected_reasons.join("; ")}</span></div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <span className="eyebrow">Evidence ledger · {d.evidence.length} entries · dates relative to t</span>
            <table className="ledger">
              <thead><tr><th>id</th><th>source</th><th>as of</th><th>≤ t</th><th>parsed</th></tr></thead>
              <tbody>
                {d.evidence.map((e) => (
                  <tr key={e.id} className={e.leak ? "leakrow" : ""}>
                    <td><code>{e.id}</code></td>
                    <td>{e.source}</td>
                    <td>{rel(e.dt_days)}</td>
                    <td>{e.leak ? <span className="leak">LEAK</span> : <span className="noleak">✓</span>}</td>
                    <td className="parsed">{Object.entries(e.parsed).filter(([, v]) => typeof v !== "object" || v === null).slice(0, 9).map(([k, v]) => <span key={k}><i>{k}</i> {short(v)}</span>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
