"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { Alert } from "@/lib/types";
import { Bell, CheckCircle, AlertTriangle, Clock, Filter } from "lucide-react";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [resolveId, setResolveId] = useState<string | null>(null);
  const [resolveNotes, setResolveNotes] = useState("");

  useEffect(() => { loadAlerts(); }, [filter]);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const data = await api.listAlerts(filter || undefined);
      setAlerts(data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleResolve = async (id: string) => {
    try {
      await api.resolveAlert(id, resolveNotes);
      setResolveId(null);
      setResolveNotes("");
      loadAlerts();
    } catch { /* ignore */ }
  };

  const statusIcon = (s: string) => {
    if (s === "unread") return <AlertTriangle size={14} color="#EF4444" />;
    if (s === "resolved") return <CheckCircle size={14} color="#22C55E" />;
    return <Clock size={14} color="#F59E0B" />;
  };

  const ruleLabel = (r: string) => {
    if (r === "comorbid_auto") return "Comorbid Auto-Alert";
    if (r === "high_risk_depression") return "High Depression Risk";
    if (r === "high_risk_anxiety") return "High Anxiety Risk";
    return r;
  };

  return (
    <>
      <div className="page-header">
        <h1><Bell size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />Alerts Center</h1>
        <p>High-risk patient notifications and clinical follow-up tracking</p>
      </div>
      <div className="page-body">
        {/* Filters */}
        <div className="card" style={{ padding: "12px 20px", marginBottom: 16, display: "flex", gap: 10, alignItems: "center" }}>
          <Filter size={14} color="var(--text-tertiary)" />
          {["", "unread", "resolved", "escalated"].map((f) => (
            <button key={f} className={`btn ${filter === f ? "btn-primary" : "btn-secondary"}`}
              style={{ fontSize: 12, padding: "4px 12px" }} onClick={() => setFilter(f)}>
              {f || "All"}
            </button>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-tertiary)" }}>
            {alerts.length} alert{alerts.length !== 1 ? "s" : ""}
          </span>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}><div className="spinner" /></div>
        ) : alerts.length === 0 ? (
          <div className="card" style={{ padding: 40, textAlign: "center" }}>
            <CheckCircle size={40} color="#22C55E" style={{ margin: "0 auto 12px" }} />
            <p style={{ color: "var(--text-tertiary)" }}>No alerts to display.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {alerts.map((a) => (
              <div key={a.id} className="card" style={{
                padding: "14px 20px",
                borderLeft: `4px solid ${a.status === "unread" ? "#EF4444" : a.status === "resolved" ? "#22C55E" : "#F59E0B"}`,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    {statusIcon(a.status)}
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{a.patient_code || "Patient"}</span>
                    <span className={`badge ${a.risk_tier === "comorbid" ? "badge-high" : "badge-moderate"}`}>
                      {(a.risk_tier || "").replace("_", " ").toUpperCase()}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--text-tertiary)", background: "var(--bg-secondary)", padding: "2px 8px", borderRadius: 4 }}>
                      {ruleLabel(a.triggered_by_rule)}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {a.depression_prob != null && (
                      <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                        Dep: {(a.depression_prob * 100).toFixed(0)}% | Anx: {((a.anxiety_prob || 0) * 100).toFixed(0)}%
                      </span>
                    )}
                    <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                </div>
                {a.status === "unread" && (
                  <div style={{ marginTop: 10 }}>
                    {resolveId === a.id ? (
                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <input className="input" placeholder="Resolution notes..." value={resolveNotes}
                          onChange={(e) => setResolveNotes(e.target.value)} style={{ flex: 1, fontSize: 12 }} />
                        <button className="btn btn-primary" style={{ fontSize: 12 }} onClick={() => handleResolve(a.id)}>
                          Resolve
                        </button>
                        <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => setResolveId(null)}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button className="btn btn-secondary" style={{ fontSize: 11 }} onClick={() => setResolveId(a.id)}>
                        <CheckCircle size={12} /> Mark Resolved
                      </button>
                    )}
                  </div>
                )}
                {a.status === "resolved" && a.notes && (
                  <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 6, fontStyle: "italic" }}>
                    Resolved: {a.notes}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
