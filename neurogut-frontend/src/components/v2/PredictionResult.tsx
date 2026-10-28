"use client";
// Result card for one NeuroGut v2 prediction (Parkinson's or schizophrenia).
import type { V2Prediction } from "@/lib/typesV2";
import { COBALT, TEAL, Bars } from "@/components/v2/ui";

export const DISEASE_NAME = { scz: "Schizophrenia", pd: "Parkinson's disease" } as const;
const TIER = {
  low: { label: "Low", cls: "badge-healthy" },
  moderate: { label: "Moderate", cls: "badge-moderate" },
  high: { label: "High", cls: "badge-high" },
} as const;

export function TierBadge({ tier }: { tier: V2Prediction["risk_tier"] }) {
  return <span className={`badge ${TIER[tier].cls}`}>{TIER[tier].label}</span>;
}

function Gauge({ p, color }: { p: number; color: string }) {
  // Semicircle dial, 0 % left to 100 % right
  const a = Math.PI * (1 - p);
  const x = 60 + 48 * Math.cos(a), y = 60 - 48 * Math.sin(a);
  return (
    <svg viewBox="0 0 120 70" width={150} aria-label={`score ${Math.round(p * 100)}%`}>
      <defs><linearGradient id="ng-g" gradientUnits="userSpaceOnUse" x1="12" x2="108" y1="0" y2="0"><stop offset="0" stopColor={TEAL} /><stop offset="1" stopColor={COBALT} /></linearGradient></defs>
      <path d="M12 60 A48 48 0 0 1 108 60" fill="none" stroke="var(--bg-tertiary)" strokeWidth={10} strokeLinecap="round" />
      <path d={`M12 60 A48 48 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}`} fill="none" stroke="url(#ng-g)" strokeWidth={10} strokeLinecap="round" />
      <text x={60} y={58} textAnchor="middle" fontSize={20} fontWeight={800} fill={color}>{Math.round(p * 100)}%</text>
    </svg>
  );
}

export default function PredictionResult({ r }: { r: V2Prediction }) {
  const pct = Math.round(r.probability * 100);
  const name = DISEASE_NAME[r.disease];
  return (
    <div className="card v2-section animate-fade-in v2-print">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <span className={`v2-pill ${r.disease === "scz" ? "cobalt" : "teal"}`}>{name}</span>
          <h3 style={{ marginTop: 8 }}>{r.patient_code || r.sample_label || "Sample"}</h3>
          <p className="sub" style={{ margin: 0 }}>
            {r.input_method.replace("_", " ")} · model {r.model_version}
            {r.missing_taxa > 0 && ` · ${r.missing_taxa} taxa not given (treated as not detected)`}
            {r.collection_date && ` · collected ${r.collection_date}`}
            {r.created_at && ` · scored ${r.created_at.slice(0, 16).replace("T", " ")}`}
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <Gauge p={r.probability} color={r.disease === "scz" ? COBALT : TEAL} />
          <div style={{ fontSize: 12, color: "var(--text-secondary)", margin: "4px 0" }}>{name}-like profile score</div>
          <TierBadge tier={r.risk_tier} />
          <div className="no-print" style={{ marginTop: 8 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => window.print()}>Print / Save as PDF</button>
          </div>
        </div>
      </div>

      <div style={{ margin: "16px 0 6px", height: 10, borderRadius: 6, background: "var(--bg-tertiary)", position: "relative" }}>
        {/* teal (healthy) on the left to cobalt (disease) on the right; the fill shows only the part up to the score */}
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 6,
          background: `linear-gradient(90deg, ${TEAL}, ${COBALT})`, backgroundSize: `${pct ? 10000 / pct : 100}% 100%` }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-tertiary)" }}>
        <span>healthy-like</span><span>{r.label ? `above decision threshold` : `below decision threshold`}</span><span>{name.toLowerCase()}-like</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 2fr) minmax(200px, 1fr)", gap: 16, marginTop: 16 }}>
        <div>
          <div className="nav-section-title" style={{ padding: 0, marginBottom: 6 }}>What moved this score</div>
          <Bars horizontal height={260} yTitle="effect on score (percentage points)" refLine={0} series={[{
            name: "push", x: r.drivers.map((d) => d.taxon.replace(/^[a-z]__/, "").replace(/_/g, " ")),
            y: r.drivers.map((d) => Math.round(d.push * 1000) / 10), color: r.drivers.map((d) => (d.push > 0 ? COBALT : TEAL)),
          }]} />
          <table className="data-table" style={{ fontSize: 11 }}>
            <thead><tr><th>Taxon</th><th>Sample %</th><th>Healthy median %</th></tr></thead>
            <tbody>{r.drivers.map((d) => (
              <tr key={d.taxon}><td>{d.taxon.replace(/^[a-z]__/, "").replace(/_/g, " ")}</td>
                <td>{d.value_pct.toFixed(3)}</td><td>{d.healthy_median_pct.toFixed(3)}</td></tr>))}
            </tbody>
          </table>
          <p className="v2-foot">Effect = how much the score changes if that taxon were at the healthy average.
            Cobalt raises the {r.disease === "scz" ? "schizophrenia" : "Parkinson's"} score, teal lowers it.</p>
        </div>
        <div>
          <div className="nav-section-title" style={{ padding: 0, marginBottom: 6 }}>Model breakdown</div>
          {Object.entries(r.model_probs).map(([m, p]) => (
            <div key={m} style={{ fontSize: 12, marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}><span>{m}</span><b>{Math.round(p * 100)}%</b></div>
              <div style={{ height: 6, background: "var(--bg-tertiary)", borderRadius: 4 }}>
                <div style={{ width: `${p * 100}%`, height: "100%", background: COBALT, opacity: 0.75, borderRadius: 4 }} />
              </div>
            </div>
          ))}
          <p className="v2-foot">Research tool, not a diagnosis. Validated AUC on unseen cohorts is about 0.6.</p>
        </div>
      </div>
    </div>
  );
}
