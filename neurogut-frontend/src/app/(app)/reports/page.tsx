"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Report } from "@/lib/types";
import { FileText, Download, Calendar } from "lucide-react";

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listReports()
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Reports</h1>
        <p>Generated clinical PDF reports</p>
      </div>

      <div className="page-body">
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
            <div className="spinner" />
          </div>
        ) : reports.length === 0 ? (
          <div className="card" style={{ padding: 60, textAlign: "center" }}>
            <FileText size={40} style={{ color: "var(--text-tertiary)", marginBottom: 12 }} />
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>No reports yet</h3>
            <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
              Run an analysis and click &quot;Download Clinical PDF Report&quot; to generate one.
            </p>
          </div>
        ) : (
          <div className="card" style={{ overflow: "hidden" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Report ID</th>
                  <th>Prediction</th>
                  <th>Version</th>
                  <th>Generated</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id}>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>
                      {r.id.slice(0, 12)}...
                    </td>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>
                      {r.prediction_id.slice(0, 12)}...
                    </td>
                    <td><span className="badge badge-info">v{r.report_version}</span></td>
                    <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                      {r.created_at ? new Date(r.created_at).toLocaleString() : "--"}
                    </td>
                    <td>
                      <a
                        href={api.getReportDownloadUrl(r.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-primary btn-sm"
                      >
                        <Download size={13} /> Download
                      </a>
                    </td>
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
