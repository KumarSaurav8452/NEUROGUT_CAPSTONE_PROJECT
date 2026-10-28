"use client";
import { useEffect, useMemo, useState } from "react";
import { FlaskConical, Upload, Download, Keyboard } from "lucide-react";
import { api } from "@/lib/api";
import type { Patient } from "@/lib/types";
import type { Disease, V2Model, V2Prediction, V2CsvResult } from "@/lib/typesV2";
import { Header, Metric } from "@/components/v2/ui";
import demo from "@/data/v2/demo.json";
import PredictionResult, { TierBadge, DISEASE_NAME } from "@/components/v2/PredictionResult";

const pretty = (t: string) => t.replace(/^[a-z]__/, "").replace(/_/g, " ");
const RANK: Record<string, string> = { s: "species", g: "genus", f: "family" };

export default function V2PredictPage() {
  const [models, setModels] = useState<V2Model[]>([]);
  const [disease, setDisease] = useState<Disease>("scz");
  const [mode, setMode] = useState<"manual" | "upload">("manual");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientId, setPatientId] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [values, setValues] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<V2Prediction | null>(null);
  const [batch, setBatch] = useState<V2CsvResult | null>(null);
  const [picked, setPicked] = useState<V2Prediction | null>(null);

  useEffect(() => {
    api.getV2Models().then(setModels).catch((e) => setError(e.message));
    api.listPatients(1, 100).then((r) => setPatients(r.patients)).catch(() => {});
  }, []);

  const model = useMemo(() => models.find((m) => m.disease === disease), [models, disease]);

  const switchDisease = (d: Disease) => { setDisease(d); setValues({}); setResult(null); setBatch(null); setPicked(null); setError(""); };

  const fillMedians = () => model && setValues(Object.fromEntries(model.features.map((f) => [f.name, String(f.healthy_median_pct)])));

  async function run() {
    setBusy(true); setError(""); setResult(null); setBatch(null); setPicked(null);
    try {
      if (mode === "manual") {
        const abundances = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim() !== "").map(([k, v]) => [k, Number(v)]));
        if (Object.keys(abundances).length === 0) throw new Error("Enter at least one abundance value");
        setResult(await api.predictV2({ disease, patient_id: patientId || undefined, collection_date: date, abundances }));
      } else {
        if (!file) throw new Error("Choose a CSV or MetaPhlAn profile file");
        const r = await api.predictV2Csv(disease, file, patientId || undefined);
        setBatch(r);
        setPicked(r.results[0] ?? null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Prediction failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Header title="New Prediction" sub="Score a gut microbiome profile for Parkinson's disease or schizophrenia"
        icon={<FlaskConical size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />} />
      <div className="page-body">
        <div className="card" style={{ padding: "12px 20px", marginBottom: 16, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {(["scz", "pd"] as Disease[]).map((d) => (
            <button key={d} className={`btn ${disease === d ? "btn-primary" : "btn-secondary"}`} onClick={() => switchDisease(d)}>
              {DISEASE_NAME[d]}
            </button>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-tertiary)" }}>
            {model ? `${model.features.length} taxa · trained on ${model.n_train} samples (${model.n_cases} cases)` : "loading model…"}
          </span>
        </div>

        {model && (
          <div className="v2-grid">
            <Metric k="Internal AUC" v={model.metrics.internal_auc.toFixed(2)} s="5-fold CV of this exact model" />
            <Metric k="New-cohort AUC" v={model.metrics.external_auc != null ? model.metrics.external_auc.toFixed(2) : "n/a"}
              s={model.metrics.external_auc != null ? "leave-one-study-out" : "single cohort: not measurable"} teal />
            <Metric k="Decision threshold" v={model.threshold.toFixed(2)} s={`balanced accuracy ${model.metrics.balanced_accuracy_at_threshold.toFixed(2)}`} />
          </div>
        )}

        <div className="card v2-section">
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 14 }}>
            <div style={{ minWidth: 220 }}>
              <label className="label">Patient (optional)</label>
              <select className="input" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
                <option value="">— not linked / match by patient_code —</option>
                {patients.map((p) => <option key={p.id} value={p.id}>{p.patient_code}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Collection date</label>
              <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button className={`btn btn-sm ${mode === "manual" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("manual")}><Keyboard size={14} /> Enter values</button>
              <button className={`btn btn-sm ${mode === "upload" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("upload")}><Upload size={14} /> Upload file</button>
            </div>
          </div>

          {mode === "manual" && model && (
            <>
              <p className="sub">Relative abundance in % (as in MetaPhlAn output). Leave a taxon empty if it was not detected.
                <button className="btn btn-ghost btn-sm" style={{ marginLeft: 8 }} onClick={fillMedians}>Fill healthy medians</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setValues({})}>Clear</button></p>
              <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                {Object.entries((demo as Record<string, Record<string, Record<string, number>>>)[disease]).map(([label, sample]) => (
                  <button key={label} className="btn btn-secondary btn-sm" onClick={() => setValues(Object.fromEntries(Object.entries(sample).map(([k, v]) => [k, String(v)])))}>
                    Load {label.toLowerCase()} sample
                  </button>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "8px 16px" }}>
                {model.features.map((f) => (
                  <div key={f.name}>
                    <label className="label" style={{ fontSize: 11, display: "flex", justifyContent: "space-between" }}>
                      <span title={f.lineage}>{pretty(f.name)}</span>
                      <span style={{ color: f.higher_in === "disease" ? "var(--primary)" : "var(--accent-dark)" }}>{RANK[f.rank] ?? f.rank}</span>
                    </label>
                    <input className="input" type="number" min={0} max={100} step="any" placeholder={`healthy ≈ ${f.healthy_median_pct}`}
                      value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
                  </div>
                ))}
              </div>
            </>
          )}

          {mode === "upload" && (
            <div>
              <p className="sub">Either a CSV with one row per sample (<code>patient_code</code>, <code>collection_date</code>, then the model taxa in %),
                or a MetaPhlAn profile / merged table (rows = clades, columns = samples). Rows whose <code>patient_code</code> matches a patient are linked to them.</p>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <input type="file" accept=".csv,.tsv,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                <button className="btn btn-secondary btn-sm" onClick={() => api.downloadV2Template(disease).catch((e) => setError(e.message))}>
                  <Download size={14} /> Template CSV
                </button>
              </div>
            </div>
          )}

          <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
            <button className="btn btn-primary" disabled={busy || !model} onClick={run}>
              {busy ? "Scoring…" : `Run ${DISEASE_NAME[disease]} prediction`}
            </button>
            {error && <span style={{ color: "var(--risk-high)", fontSize: 13 }}>{error}</span>}
          </div>
        </div>

        {result && <PredictionResult r={result} />}

        {batch && (
          <div className="card v2-section">
            <h3>{batch.n_predicted} samples scored ({batch.format === "profile" ? "MetaPhlAn profile" : "CSV rows"})</h3>
            {batch.errors.length > 0 && <p className="sub" style={{ color: "var(--risk-high)" }}>
              {batch.errors.length} skipped: {batch.errors.slice(0, 3).map((e) => `${e.row}: ${e.error}`).join("; ")}</p>}
            <table className="data-table">
              <thead><tr><th>Sample</th><th>Patient</th><th>Score</th><th>Tier</th><th>Missing taxa</th></tr></thead>
              <tbody>{batch.results.map((r) => (
                <tr key={r.id} onClick={() => setPicked(r)} style={{ cursor: "pointer", background: picked?.id === r.id ? "var(--primary-light)" : undefined }}>
                  <td style={{ fontWeight: 600 }}>{r.sample_label}</td><td>{r.patient_code ?? "—"}</td>
                  <td>{Math.round(r.probability * 100)}%</td><td><TierBadge tier={r.risk_tier} /></td><td>{r.missing_taxa}</td>
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
