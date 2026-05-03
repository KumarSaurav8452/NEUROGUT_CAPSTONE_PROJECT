"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { RISK_CONFIG } from "@/lib/types";
import type { PatientDetail } from "@/lib/types";
import { User, Calendar, FlaskConical, FileText } from "lucide-react";
import Link from "next/link";

export default function PatientDetailPage() {
  const params = useParams();
  const [patient, setPatient] = useState<PatientDetail | null>(null);

  useEffect(() => {
    if (params.id) {
      api.getPatient(params.id as string).then(setPatient).catch(() => {});
    }
  }, [params.id]);

  if (!patient) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>Patient: {patient.patient_code}</h1>
        <p>Patient profile and analysis history</p>
      </div>

      <div className="page-body">
        {/* Info Card */}
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 20 }}>
            <div>
              <div className="label">Patient Code</div>
              <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
                {patient.patient_code}
              </div>
            </div>
            <div>
              <div className="label">Age</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{patient.age ?? "N/A"}</div>
            </div>
            <div>
              <div className="label">Sex</div>
              <div style={{ fontSize: 16, fontWeight: 600, textTransform: "capitalize" }}>
                {patient.sex.replace("_", " ")}
              </div>
            </div>
            <div>
              <div className="label">Registered</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>
                {patient.created_at ? new Date(patient.created_at).toLocaleDateString() : "N/A"}
              </div>
            </div>
          </div>
          {patient.notes && (
            <div style={{ marginTop: 16, padding: 12, background: "var(--bg-secondary)", borderRadius: 8 }}>
              <div className="label">Notes</div>
              <p style={{ fontSize: 14, margin: 0 }}>{patient.notes}</p>
            </div>
          )}
        </div>

        {/* Samples & Predictions */}
        <div className="card" style={{ overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: 8 }}>
            <FlaskConical size={16} color="var(--primary)" />
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Analysis History</h3>
            <span className="badge badge-info" style={{ marginLeft: "auto" }}>
              {patient.samples.length} sample{patient.samples.length !== 1 ? "s" : ""}
            </span>
          </div>

          {patient.samples.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--text-tertiary)" }}>
              <FlaskConical size={32} style={{ marginBottom: 8, opacity: 0.4 }} />
              <p>No samples submitted yet.</p>
              <Link href="/analysis" className="btn btn-primary btn-sm" style={{ marginTop: 8 }}>
                Run Analysis
              </Link>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Collection Date</th>
                  <th>Method</th>
                  <th>Depression</th>
                  <th>Anxiety</th>
                  <th>Risk Tier</th>
                  <th>Analyzed</th>
                </tr>
              </thead>
              <tbody>
                {patient.samples.map((s) => {
                  const pred = s.prediction;
                  const rc = pred ? RISK_CONFIG[pred.risk_tier] : null;
                  return (
                    <tr key={s.id}>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{s.collection_date}</td>
                      <td style={{ textTransform: "capitalize" }}>{s.input_method.replace("_", " ")}</td>
                      <td>{pred ? `${(pred.depression_prob * 100).toFixed(1)}%` : "--"}</td>
                      <td>{pred ? `${(pred.anxiety_prob * 100).toFixed(1)}%` : "--"}</td>
                      <td>{rc ? <span className={`badge ${rc.badge}`}>{rc.label}</span> : "--"}</td>
                      <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                        {pred?.created_at ? new Date(pred.created_at).toLocaleDateString() : "--"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
