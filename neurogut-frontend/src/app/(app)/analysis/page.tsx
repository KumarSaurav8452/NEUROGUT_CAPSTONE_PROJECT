"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { TAXA_NAMES, TAXA_DISPLAY, RISK_CONFIG, TAXA_CLINICAL_INFO } from "@/lib/types";
import type { PredictionInput, PredictionResult, Patient } from "@/lib/types";
import { FlaskConical, Download, RotateCcw, Brain, Heart, Users } from "lucide-react";
import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const DEFAULT_VALUES: PredictionInput = {
  lachnospira: 5.0, ruthenibacterium: 5.0, veillonella: 3.0,
  gardnerella: -2.0, pseudobutyrivibrio: 1.0, kocuria: -1.0,
  trueperella: 0.5, lancefieldella: -2.0, fructilactobacillus: -2.0,
  lachnoanaerobaculum: 1.0, corynebacterium: 0.5, raoultella: -2.0,
  lawsonella: -1.0,
};

export default function AnalysisPage() {
  const [values, setValues] = useState<PredictionInput>({ ...DEFAULT_VALUES });
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reportLoading, setReportLoading] = useState(false);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState("");

  // Load patients on mount
  useEffect(() => {
    api.listPatients(1, 100).then((r) => setPatients(r.patients)).catch(() => {});
  }, []);

  const handlePredict = async () => {
    setLoading(true);
    setError("");
    try {
      // If a patient is selected, create a sample first so it links to their history
      let sampleId: string | undefined;
      if (selectedPatientId) {
        const sample = await api.submitSample({
          patient_id: selectedPatientId,
          collection_date: new Date().toISOString().split("T")[0],
          input_method: "manual",
          ...values,
        });
        sampleId = sample.id;
      }
      const r = await api.predict(values, sampleId);
      setResult(r);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Prediction failed");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setValues({ ...DEFAULT_VALUES });
    setResult(null);
    setError("");
  };

  const handleDownloadReport = async () => {
    if (!result) return;
    setReportLoading(true);
    try {
      const report = await api.generateReport(result.prediction_id);
      window.open(api.getReportDownloadUrl(report.id), "_blank");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setReportLoading(false);
    }
  };

  const riskConfig = result ? RISK_CONFIG[result.risk_tier] : null;

  // Prepare chart data from result
  const rfKeys = result ? Object.keys(result.rf_importances) : [];
  const rfVals = result ? Object.values(result.rf_importances) : [];
  const xgbVals = result ? rfKeys.map(k => result.xgb_importances[k] || 0) : [];
  const rfTop5 = result ? new Set(
    [...rfKeys].sort((a, b) => (result.rf_importances[b] || 0) - (result.rf_importances[a] || 0)).slice(0, 5)
  ) : new Set<string>();
  const xgbTop5 = result ? new Set(
    [...rfKeys].sort((a, b) => (result.xgb_importances[b] || 0) - (result.xgb_importances[a] || 0)).slice(0, 5)
  ) : new Set<string>();

  return (
    <>
      <div className="page-header">
        <h1>New Microbiome Analysis</h1>
        <p>Enter 13 bacterial taxa abundances to predict Depression &amp; Anxiety risk</p>
      </div>

      <div className="page-body">
        <div style={{ display: "grid", gridTemplateColumns: result ? "380px 1fr" : "1fr", gap: 24 }}>
          {/* ── Input Panel ── */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
              <FlaskConical size={18} color="var(--primary)" />
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Taxa Abundances</h2>
            </div>

            {/* Patient Selector */}
            <div style={{ marginBottom: 16, padding: 12, background: "var(--bg-secondary)", borderRadius: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                <Users size={14} color="var(--primary)" />
                <label className="label" style={{ margin: 0 }}>Link to Patient (optional)</label>
              </div>
              <select
                className="input"
                value={selectedPatientId}
                onChange={(e) => setSelectedPatientId(e.target.value)}
              >
                <option value="">-- Standalone Analysis --</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.patient_code} {p.age ? `(Age ${p.age})` : ""} {p.sex !== "prefer_not_to_say" ? `- ${p.sex}` : ""}
                  </option>
                ))}
              </select>
              {selectedPatientId && (
                <p style={{ fontSize: 11, color: "var(--primary)", marginTop: 4, marginBottom: 0 }}>
                  Results will appear in this patient&apos;s Analysis History
                </p>
              )}
            </div>

            <div style={{ display: "grid", gap: 4 }}>
              {TAXA_NAMES.map((taxa) => (
                <div key={taxa} className="taxa-slider">
                  <div className="taxa-header">
                    <span className="taxa-name">{TAXA_DISPLAY[taxa]}</span>
                    <span className="taxa-value">{values[taxa].toFixed(1)}</span>
                  </div>
                  <input type="range" min="-10" max="15" step="0.1" value={values[taxa]}
                    onChange={(e) => setValues({ ...values, [taxa]: parseFloat(e.target.value) })} />
                </div>
              ))}
            </div>
            {error && (
              <div style={{ padding: "10px 14px", marginTop: 16, background: "#FEF2F2", border: "1px solid #FCA5A5", borderRadius: 8, color: "#DC2626", fontSize: 13 }}>
                {error}
              </div>
            )}
            <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
              <button className="btn btn-primary" onClick={handlePredict} disabled={loading} style={{ flex: 1 }}>
                {loading ? <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> : <><FlaskConical size={15} /> Analyze</>}
              </button>
              <button className="btn btn-secondary" onClick={handleReset}>
                <RotateCcw size={15} />
              </button>
            </div>
          </div>

          {/* ── Results Panel ── */}
          {result && riskConfig && (
            <div className="animate-fade-in" style={{ display: "grid", gap: 16 }}>
              {/* Row 1: Risk Banner + Probability Cards */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                {/* Risk Tier */}
                <div className="card risk-card" style={{ borderLeft: `4px solid ${riskConfig.color}`, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                  <div className="risk-label">Risk Tier</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: riskConfig.color, margin: "8px 0" }}>
                    {riskConfig.label}
                  </div>
                  <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                    {result.processing_time_ms}ms | {result.model_version}
                  </span>
                </div>
                {/* Depression */}
                <div className="card risk-card">
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Brain size={15} color={result.depression_label ? "#F59E0B" : "#22C55E"} />
                    <span className="risk-label">Depression</span>
                  </div>
                  <div className="risk-prob" style={{ color: result.depression_label ? "#F59E0B" : "#22C55E", fontSize: 36 }}>
                    {(result.depression_prob * 100).toFixed(1)}%
                  </div>
                  {result.depression_ci_low != null && (
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginBottom: 4 }}>
                      95% CI: {(result.depression_ci_low * 100).toFixed(1)}% – {((result.depression_ci_high ?? 0) * 100).toFixed(1)}%
                    </div>
                  )}
                  <span className={`badge ${result.depression_label ? "badge-moderate" : "badge-healthy"}`}>
                    {result.depression_label ? "POSITIVE" : "NEGATIVE"}
                  </span>
                  <div className="risk-bar" style={{ marginTop: 8, position: "relative" }}>
                    <div className="risk-bar-fill" style={{
                      width: `${result.depression_prob * 100}%`,
                      background: result.depression_label ? "linear-gradient(90deg, #F59E0B, #EF4444)" : "linear-gradient(90deg, #22C55E, #10B981)",
                    }} />
                    {result.depression_ci_low != null && (
                      <div style={{
                        position: "absolute", top: 0, height: "100%",
                        left: `${(result.depression_ci_low ?? 0) * 100}%`,
                        width: `${((result.depression_ci_high ?? 0) - (result.depression_ci_low ?? 0)) * 100}%`,
                        background: "rgba(0,0,0,0.08)", borderRadius: 4,
                      }} />
                    )}
                  </div>
                </div>
                {/* Anxiety */}
                <div className="card risk-card">
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Heart size={15} color={result.anxiety_label ? "#F59E0B" : "#22C55E"} />
                    <span className="risk-label">Anxiety</span>
                  </div>
                  <div className="risk-prob" style={{ color: result.anxiety_label ? "#F59E0B" : "#22C55E", fontSize: 36 }}>
                    {(result.anxiety_prob * 100).toFixed(1)}%
                  </div>
                  {result.anxiety_ci_low != null && (
                    <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginBottom: 4 }}>
                      95% CI: {(result.anxiety_ci_low * 100).toFixed(1)}% – {((result.anxiety_ci_high ?? 0) * 100).toFixed(1)}%
                    </div>
                  )}
                  <span className={`badge ${result.anxiety_label ? "badge-moderate" : "badge-healthy"}`}>
                    {result.anxiety_label ? "POSITIVE" : "NEGATIVE"}
                  </span>
                  <div className="risk-bar" style={{ marginTop: 8, position: "relative" }}>
                    <div className="risk-bar-fill" style={{
                      width: `${result.anxiety_prob * 100}%`,
                      background: result.anxiety_label ? "linear-gradient(90deg, #F59E0B, #EF4444)" : "linear-gradient(90deg, #22C55E, #10B981)",
                    }} />
                    {result.anxiety_ci_low != null && (
                      <div style={{
                        position: "absolute", top: 0, height: "100%",
                        left: `${(result.anxiety_ci_low ?? 0) * 100}%`,
                        width: `${((result.anxiety_ci_high ?? 0) - (result.anxiety_ci_low ?? 0)) * 100}%`,
                        background: "rgba(0,0,0,0.08)", borderRadius: 4,
                      }} />
                    )}
                  </div>
                </div>
              </div>

              {/* Row 2: Risk Gauge Charts */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="card" style={{ padding: "12px 16px" }}>
                  <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 4, textAlign: "center" }}>Depression Risk Gauge</h3>
                  <Plot
                    data={[{
                      type: "indicator",
                      mode: "gauge+number",
                      value: result.depression_prob * 100,
                      number: { suffix: "%", font: { size: 28 } },
                      gauge: {
                        axis: { range: [0, 100], tickwidth: 1 },
                        bar: { color: result.depression_prob > 0.5 ? "#EF4444" : "#22C55E", thickness: 0.7 },
                        bgcolor: "#F3F4F6",
                        steps: [
                          { range: [0, 30], color: "#DCFCE7" },
                          { range: [30, 60], color: "#FEF9C3" },
                          { range: [60, 100], color: "#FEE2E2" },
                        ],
                        threshold: { line: { color: "#1A1A2E", width: 3 }, thickness: 0.8, value: 50 },
                      },
                    }]}
                    layout={{ height: 200, margin: { t: 10, b: 10, l: 30, r: 30 }, paper_bgcolor: "transparent", font: { family: "Inter" } }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: "100%" }}
                  />
                </div>
                <div className="card" style={{ padding: "12px 16px" }}>
                  <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 4, textAlign: "center" }}>Anxiety Risk Gauge</h3>
                  <Plot
                    data={[{
                      type: "indicator",
                      mode: "gauge+number",
                      value: result.anxiety_prob * 100,
                      number: { suffix: "%", font: { size: 28 } },
                      gauge: {
                        axis: { range: [0, 100], tickwidth: 1 },
                        bar: { color: result.anxiety_prob > 0.5 ? "#EF4444" : "#22C55E", thickness: 0.7 },
                        bgcolor: "#F3F4F6",
                        steps: [
                          { range: [0, 30], color: "#DCFCE7" },
                          { range: [30, 60], color: "#FEF9C3" },
                          { range: [60, 100], color: "#FEE2E2" },
                        ],
                        threshold: { line: { color: "#1A1A2E", width: 3 }, thickness: 0.8, value: 50 },
                      },
                    }]}
                    layout={{ height: 200, margin: { t: 10, b: 10, l: 30, r: 30 }, paper_bgcolor: "transparent", font: { family: "Inter" } }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: "100%" }}
                  />
                </div>
              </div>

              {/* Row 3: Dysbiosis Heatmap */}
              <div className="card" style={{ padding: "16px 20px" }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>Dysbiosis Heatmap</h3>
                <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 8 }}>
                  Taxa abundance levels colored by deviation from healthy baseline. Red = elevated, Blue = depleted.
                </p>
                <Plot
                  data={[{
                    type: "heatmap",
                    z: [TAXA_NAMES.map(t => values[t])],
                    x: TAXA_NAMES.map(t => TAXA_DISPLAY[t]),
                    y: ["Patient Sample"],
                    colorscale: [
                      [0, "#2563EB"],
                      [0.3, "#93C5FD"],
                      [0.5, "#F9FAFB"],
                      [0.7, "#FCA5A5"],
                      [1, "#DC2626"],
                    ],
                    showscale: true,
                    colorbar: { title: "Abundance", titleside: "right", thickness: 12, len: 0.9 },
                    hoverongaps: false,
                    text: [TAXA_NAMES.map(t => `${TAXA_DISPLAY[t]}: ${values[t].toFixed(2)}`)],
                    hoverinfo: "text",
                  }]}
                  layout={{
                    height: 140,
                    margin: { t: 10, b: 80, l: 100, r: 80 },
                    paper_bgcolor: "transparent",
                    plot_bgcolor: "transparent",
                    xaxis: { tickangle: -45, tickfont: { size: 10, family: "Inter" } },
                    yaxis: { tickfont: { size: 11 } },
                    font: { family: "Inter" },
                  }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: "100%" }}
                />
              </div>

              {/* Row 4: Radar + Bar Chart */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {/* Biomarker Radar */}
                <div className="card" style={{ padding: "16px 20px" }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Biomarker Importance Radar</h3>
                  <Plot
                    data={[
                      {
                        type: "scatterpolar",
                        r: rfVals,
                        theta: rfKeys,
                        fill: "toself",
                        name: "Random Forest",
                        fillcolor: "rgba(0,109,119,0.15)",
                        line: { color: "#006D77", width: 2 },
                      },
                      {
                        type: "scatterpolar",
                        r: xgbVals,
                        theta: rfKeys,
                        fill: "toself",
                        name: "XGBoost Chain",
                        fillcolor: "rgba(239,68,68,0.1)",
                        line: { color: "#EF4444", width: 2 },
                      },
                    ]}
                    layout={{
                      polar: { radialaxis: { visible: true, range: [0, Math.max(...rfVals, ...xgbVals) * 1.3] } },
                      showlegend: true,
                      legend: { x: 0, y: -0.15, orientation: "h" as const, font: { size: 10 } },
                      margin: { t: 20, b: 50, l: 50, r: 50 },
                      height: 320,
                      paper_bgcolor: "transparent",
                      plot_bgcolor: "transparent",
                      font: { family: "Inter", size: 9 },
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: "100%" }}
                  />
                </div>

                {/* Horizontal Bar Chart */}
                <div className="card" style={{ padding: "16px 20px" }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Feature Importance Comparison</h3>
                  <Plot
                    data={[
                      {
                        type: "bar",
                        y: rfKeys,
                        x: rfVals,
                        orientation: "h" as const,
                        name: "Random Forest",
                        marker: { color: "#006D77" },
                      },
                      {
                        type: "bar",
                        y: rfKeys,
                        x: xgbVals,
                        orientation: "h" as const,
                        name: "XGBoost Chain",
                        marker: { color: "#EF4444" },
                      },
                    ]}
                    layout={{
                      barmode: "group",
                      showlegend: true,
                      legend: { x: 0.5, y: -0.12, orientation: "h" as const, xanchor: "center", font: { size: 10 } },
                      margin: { t: 10, b: 50, l: 110, r: 20 },
                      height: 320,
                      paper_bgcolor: "transparent",
                      plot_bgcolor: "transparent",
                      xaxis: { title: "Importance", titlefont: { size: 11 } },
                      yaxis: { tickfont: { size: 10, family: "JetBrains Mono, monospace" }, autorange: "reversed" as const },
                      font: { family: "Inter" },
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: "100%" }}
                  />
                </div>
              </div>

              {/* Row 5: Venn Diagram + Consensus */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {/* Venn Diagram (CSS-based) */}
                <div className="card" style={{ padding: "16px 20px" }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Top-5 Feature Overlap (Venn)</h3>
                  <div style={{ position: "relative", height: 220, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {/* RF circle */}
                    <div style={{
                      position: "absolute", left: "15%", width: 180, height: 180, borderRadius: "50%",
                      background: "rgba(0,109,119,0.12)", border: "2px solid #006D77",
                      display: "flex", flexDirection: "column", alignItems: "flex-start", justifyContent: "center", paddingLeft: 16,
                    }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: "#006D77", marginBottom: 6 }}>RF Only</div>
                      {[...rfTop5].filter(f => !xgbTop5.has(f)).map(f => (
                        <div key={f} style={{ fontSize: 10, color: "#006D77", lineHeight: 1.5 }}>{f}</div>
                      ))}
                    </div>
                    {/* XGB circle */}
                    <div style={{
                      position: "absolute", right: "15%", width: 180, height: 180, borderRadius: "50%",
                      background: "rgba(239,68,68,0.08)", border: "2px solid #EF4444",
                      display: "flex", flexDirection: "column", alignItems: "flex-end", justifyContent: "center", paddingRight: 16,
                    }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: "#EF4444", marginBottom: 6 }}>XGB Only</div>
                      {[...xgbTop5].filter(f => !rfTop5.has(f)).map(f => (
                        <div key={f} style={{ fontSize: 10, color: "#EF4444", lineHeight: 1.5 }}>{f}</div>
                      ))}
                    </div>
                    {/* Overlap center */}
                    <div style={{
                      position: "absolute", zIndex: 2, textAlign: "center",
                      background: "rgba(168, 85, 247, 0.08)", borderRadius: 8, padding: "8px 12px",
                    }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: "#7C3AED", marginBottom: 4 }}>Consensus</div>
                      {result.consensus_features.length > 0
                        ? result.consensus_features.map(f => (
                            <div key={f} style={{ fontSize: 11, fontWeight: 600, color: "#7C3AED", lineHeight: 1.6 }}>{f}</div>
                          ))
                        : <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>None</div>
                      }
                    </div>
                  </div>
                </div>

                {/* Abundance Profile Bar */}
                <div className="card" style={{ padding: "16px 20px" }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Taxa Abundance Profile</h3>
                  <Plot
                    data={[{
                      type: "bar",
                      x: TAXA_NAMES.map(t => TAXA_DISPLAY[t]),
                      y: TAXA_NAMES.map(t => values[t]),
                      marker: {
                        color: TAXA_NAMES.map(t =>
                          result.consensus_features.includes(TAXA_DISPLAY[t]) ? "#7C3AED"
                          : values[t] > 3 ? "#EF4444"
                          : values[t] < -2 ? "#3B82F6"
                          : "#9CA3AF"
                        ),
                      },
                      hovertext: TAXA_NAMES.map(t =>
                        `${TAXA_DISPLAY[t]}: ${values[t].toFixed(2)}${result.consensus_features.includes(TAXA_DISPLAY[t]) ? " (Consensus)" : ""}`
                      ),
                      hoverinfo: "text",
                    }]}
                    layout={{
                      height: 220,
                      margin: { t: 10, b: 80, l: 40, r: 10 },
                      paper_bgcolor: "transparent",
                      plot_bgcolor: "transparent",
                      xaxis: { tickangle: -45, tickfont: { size: 9, family: "Inter" } },
                      yaxis: { title: "Abundance", titlefont: { size: 10 }, zeroline: true, zerolinecolor: "#E5E7EB" },
                      font: { family: "Inter" },
                      shapes: [{ type: "line", y0: 0, y1: 0, x0: -0.5, x1: 12.5, line: { color: "#9CA3AF", width: 1, dash: "dot" } }],
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: "100%" }}
                  />
                  <div style={{ display: "flex", gap: 16, justifyContent: "center", fontSize: 10, color: "var(--text-tertiary)" }}>
                    <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#EF4444", marginRight: 4 }} />Elevated</span>
                    <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#3B82F6", marginRight: 4 }} />Depleted</span>
                    <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#7C3AED", marginRight: 4 }} />Consensus</span>
                  </div>
                </div>
              </div>

              {/* Download Report */}
              <button className="btn btn-primary btn-lg" onClick={handleDownloadReport} disabled={reportLoading} style={{ width: "100%" }}>
                {reportLoading
                  ? <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                  : <><Download size={16} /> Download Clinical PDF Report</>
                }
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
