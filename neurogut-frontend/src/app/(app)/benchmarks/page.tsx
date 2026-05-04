"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { CohortBenchmark } from "@/lib/types";
import { BarChart3 } from "lucide-react";
import dynamic from "next/dynamic";
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const TIERS = ["healthy", "depression_only", "anxiety_only", "comorbid"];
const TIER_LABELS: Record<string, string> = {
  healthy: "Healthy", depression_only: "Depression", anxiety_only: "Anxiety", comorbid: "Comorbid",
};
const TIER_COLORS: Record<string, string> = {
  healthy: "#22C55E", depression_only: "#F59E0B", anxiety_only: "#3B82F6", comorbid: "#EF4444",
};

export default function BenchmarksPage() {
  const [benchmarks, setBenchmarks] = useState<CohortBenchmark[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTier, setSelectedTier] = useState("healthy");

  useEffect(() => {
    api.getBenchmarks().then(setBenchmarks).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const tierData = benchmarks.filter((b) => b.risk_tier === selectedTier);
  const taxa = tierData.map((b) => b.taxon_name);
  const means = tierData.map((b) => b.mean_value);
  const p25s = tierData.map((b) => b.p25_value);
  const p75s = tierData.map((b) => b.p75_value);

  return (
    <>
      <div className="page-header">
        <h1><BarChart3 size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />Cohort Benchmarks</h1>
        <p>De-identified population averages by risk tier — compare patients against hospital cohort</p>
      </div>
      <div className="page-body">
        {/* Tier selector */}
        <div className="card" style={{ padding: "12px 20px", marginBottom: 16, display: "flex", gap: 10, alignItems: "center" }}>
          {TIERS.map((t) => (
            <button key={t} className={`btn ${selectedTier === t ? "btn-primary" : "btn-secondary"}`}
              style={{ fontSize: 12, padding: "4px 14px" }} onClick={() => setSelectedTier(t)}>
              {TIER_LABELS[t]}
            </button>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-tertiary)" }}>
            {tierData.length > 0 ? `${tierData[0]?.sample_count || 0} samples in cohort` : "No data"}
          </span>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}><div className="spinner" /></div>
        ) : tierData.length === 0 ? (
          <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-tertiary)" }}>
            No benchmark data for this tier yet. Run more analyses to build cohort statistics.
          </div>
        ) : (
          <>
            {/* Box-plot style chart */}
            <div className="card" style={{ padding: "16px 20px", marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>Taxa Distribution — {TIER_LABELS[selectedTier]}</h3>
              <Plot
                data={[{
                  type: "bar", x: taxa, y: means, name: "Mean",
                  marker: { color: TIER_COLORS[selectedTier] },
                  error_y: { type: "data", symmetric: false,
                    array: p75s.map((p, i) => p - means[i]),
                    arrayminus: means.map((m, i) => m - p25s[i]),
                    color: "#6B7280", thickness: 1.5,
                  },
                }]}
                layout={{
                  height: 350, margin: { t: 20, b: 100, l: 50, r: 20 },
                  paper_bgcolor: "transparent", plot_bgcolor: "transparent",
                  xaxis: { tickangle: -45, tickfont: { size: 10, family: "Inter" } },
                  yaxis: { title: "Abundance (CLR)", titlefont: { size: 11 }, zeroline: true, zerolinecolor: "#E5E7EB" },
                  font: { family: "Inter" },
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: "100%" }}
              />
              <p style={{ fontSize: 11, color: "var(--text-tertiary)", textAlign: "center" }}>
                Bars show mean values. Error bars show P25–P75 interquartile range.
              </p>
            </div>

            {/* Data table */}
            <div className="card" style={{ overflow: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Taxon</th><th>Mean</th><th>Std Dev</th><th>P25</th><th>Median</th><th>P75</th><th>Samples</th>
                  </tr>
                </thead>
                <tbody>
                  {tierData.map((b) => (
                    <tr key={b.taxon_name}>
                      <td style={{ fontWeight: 600 }}>{b.taxon_name}</td>
                      <td>{b.mean_value.toFixed(3)}</td>
                      <td>{b.std_value.toFixed(3)}</td>
                      <td>{b.p25_value.toFixed(3)}</td>
                      <td>{b.p50_value.toFixed(3)}</td>
                      <td>{b.p75_value.toFixed(3)}</td>
                      <td>{b.sample_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}
