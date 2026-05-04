"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";
import { Shield, Download, Filter } from "lucide-react";

const ACTION_LABELS: Record<string, string> = {
  LOGIN: "Login", LOGOUT: "Logout", PATIENT_VIEW: "Patient View",
  SAMPLE_SUBMIT: "Sample Submit", PREDICTION_RUN: "Prediction Run",
  REPORT_GENERATE: "Report Generate", REPORT_DOWNLOAD: "Report Download",
  USER_INVITE: "User Invite", SETTINGS_CHANGE: "Settings Change", DATA_EXPORT: "Data Export",
};

const ACTION_COLORS: Record<string, string> = {
  LOGIN: "#3B82F6", PREDICTION_RUN: "#006D77", REPORT_GENERATE: "#7C3AED",
  REPORT_DOWNLOAD: "#7C3AED", PATIENT_VIEW: "#F59E0B", SETTINGS_CHANGE: "#EF4444",
};

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");

  useEffect(() => { loadLogs(); }, [page, actionFilter]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await api.listAuditLogs(page, actionFilter || undefined);
      setLogs(data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  return (
    <>
      <div className="page-header">
        <h1><Shield size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />Audit Log</h1>
        <p>HIPAA-grade compliance trail — all data accesses, predictions, and downloads</p>
      </div>
      <div className="page-body">
        <div className="card" style={{ padding: "12px 20px", marginBottom: 16, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <Filter size={14} color="var(--text-tertiary)" />
          <select className="input" style={{ width: 180, fontSize: 12 }} value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}>
            <option value="">All Actions</option>
            {Object.entries(ACTION_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-tertiary)" }}>
            Page {page} • {logs.length} entries
          </span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-secondary" style={{ fontSize: 11 }} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <button className="btn btn-secondary" style={{ fontSize: 11 }} disabled={logs.length < 50} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}><div className="spinner" /></div>
        ) : (
          <div className="card" style={{ overflow: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>User</th>
                  <th>Resource</th>
                  <th>IP Address</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text-tertiary)", padding: 20 }}>No audit entries found.</td></tr>
                ) : logs.map((l) => (
                  <tr key={l.id}>
                    <td style={{ fontSize: 11, whiteSpace: "nowrap" }}>
                      {l.created_at ? new Date(l.created_at).toLocaleString() : "—"}
                    </td>
                    <td>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
                        color: "white", background: ACTION_COLORS[l.action] || "#6B7280",
                      }}>
                        {ACTION_LABELS[l.action] || l.action}
                      </span>
                    </td>
                    <td style={{ fontSize: 12 }}>{l.user_email || l.user_id?.slice(0, 8) || "—"}</td>
                    <td style={{ fontSize: 11, fontFamily: "monospace" }}>
                      {l.resource_type ? `${l.resource_type}/${(l.resource_id || "").slice(0, 8)}` : "—"}
                    </td>
                    <td style={{ fontSize: 11, fontFamily: "monospace" }}>{l.ip_address || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
