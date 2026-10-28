"use client";
import { useEffect, useState } from "react";
import { History } from "lucide-react";
import { api } from "@/lib/api";
import type { Disease, V2Prediction } from "@/lib/typesV2";
import { Header, Metric } from "@/components/v2/ui";
import PredictionResult, { TierBadge, DISEASE_NAME } from "@/components/v2/PredictionResult";

export default function V2HistoryPage() {
  const [disease, setDisease] = useState<Disease | "">("");
  const [rows, setRows] = useState<V2Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [picked, setPicked] = useState<V2Prediction | null>(null);

  useEffect(() => {
    let live = true;
    api.listV2Predictions(disease || undefined)
      .then((r) => { if (live) { setRows(r); setPicked(null); } })
      .catch(() => {})
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [disease]);

  const count = (t: V2Prediction["risk_tier"]) => rows.filter((r) => r.risk_tier === t).length;

  function exportCsv() {
    const head = ["created_at", "disease", "patient_code", "sample_label", "collection_date", "input_method",
      "probability", "risk_tier", "above_threshold", "model_version"];
    const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = rows.map((r) => [r.created_at, r.disease, r.patient_code, r.sample_label, r.collection_date,
      r.input_method, r.probability, r.risk_tier, r.label, r.model_version].map(esc).join(","));
    const url = URL.createObjectURL(new Blob([[head.join(","), ...lines].join("\n")], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `neurogut_v2_predictions${disease ? "_" + disease : ""}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const filters: [Disease | "", string][] = [["", "All"], ["scz", DISEASE_NAME.scz], ["pd", DISEASE_NAME.pd]];
  return (
    <>
      <Header title="Prediction History" sub="Every v2 prediction made in this hospital, newest first"
        icon={<History size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />} />
      <div className="page-body">
        <div className="card" style={{ padding: "12px 20px", marginBottom: 16, display: "flex", gap: 10 }}>
          {filters.map(([d, l]) => (
            <button key={l} className={`btn btn-sm ${disease === d ? "btn-primary" : "btn-secondary"}`} onClick={() => setDisease(d)}>{l}</button>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-tertiary)", alignSelf: "center" }}>{rows.length} predictions</span>
          <button className="btn btn-secondary btn-sm" disabled={rows.length === 0} onClick={exportCsv}>Export CSV</button>
        </div>
        {rows.length > 0 && (
          <div className="v2-grid">
            <Metric k="High" v={String(count("high"))} s="score ≥ 65 %" />
            <Metric k="Moderate" v={String(count("moderate"))} s="35–65 %" />
            <Metric k="Low" v={String(count("low"))} s="score < 35 %" teal />
            <Metric k="Patients linked" v={String(new Set(rows.filter((r) => r.patient_id).map((r) => r.patient_id)).size)} s="distinct patients" teal />
          </div>
        )}
        {loading ? <div style={{ textAlign: "center", padding: 40 }}><div className="spinner" /></div> : rows.length === 0 ? (
          <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-tertiary)" }}>No v2 predictions yet. Run one from New Prediction.</div>
        ) : (
          <div className="card" style={{ overflow: "auto", marginBottom: 16 }}>
            <table className="data-table">
              <thead><tr><th>Date</th><th>Disease</th><th>Sample / patient</th><th>Input</th><th>Score</th><th>Tier</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.id} onClick={() => setPicked(r)} style={{ cursor: "pointer", background: picked?.id === r.id ? "var(--primary-light)" : undefined }}>
                  <td style={{ whiteSpace: "nowrap" }}>{r.created_at?.slice(0, 16).replace("T", " ")}</td>
                  <td><span className={`v2-pill ${r.disease === "scz" ? "cobalt" : "teal"}`}>{r.disease.toUpperCase()}</span></td>
                  <td style={{ fontWeight: 600 }}>{r.patient_code || r.sample_label || "—"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{r.input_method.replace("_", " ")}</td>
                  <td>{Math.round(r.probability * 100)}%</td>
                  <td><TierBadge tier={r.risk_tier} /></td>
                </tr>))}
              </tbody>
            </table>
          </div>
        )}
        {picked && <PredictionResult r={picked} />}
      </div>
    </>
  );
}
