"use client";
import { useState } from "react";
import { Download, FileJson, FileText, Filter, Info, AlertCircle } from "lucide-react";
import { RoleGuard } from "@/components/RoleGuard";
import { api } from "@/lib/api";

function ExportPageContent() {
  const [format, setFormat] = useState<"csv" | "json">("csv");
  const [tier, setTier] = useState("");
  const [exporting, setExporting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setExporting(true);
    setDone(false);
    setError(null);
    try {
      await api.exportDataset(format, tier || undefined);
      setDone(true);
      setTimeout(() => setDone(false), 4000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Export failed";
      setError(message);
      setTimeout(() => setError(null), 5000);
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Data Export</h1>
        <p>Export anonymized cohort data for research use</p>
      </div>

      <div className="page-body">
        {/* Notice */}
        <div style={{
          background: "#EFF6FF", border: "1px solid #BFDBFE",
          borderRadius: 10, padding: "14px 18px", marginBottom: 24,
          display: "flex", gap: 12, alignItems: "flex-start",
        }}>
          <Info size={18} color="#2563EB" style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <p style={{ margin: 0, fontSize: 13, color: "#1D4ED8", fontWeight: 600 }}>
              Anonymized data only
            </p>
            <p style={{ margin: "2px 0 0", fontSize: 13, color: "#3B82F6" }}>
              All exports automatically strip patient identifiers (name, DOB, NHS number).
              Samples are referenced by anonymized cohort codes only, per data governance policy.
            </p>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Export Config */}
          <div className="card" style={{ padding: 28 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Export Options</h3>

            <div style={{ marginBottom: 18 }}>
              <label className="label">Format</label>
              <div style={{ display: "flex", gap: 10 }}>
                {[
                  { value: "csv", label: "CSV", icon: FileText },
                  { value: "json", label: "JSON", icon: FileJson },
                ].map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    onClick={() => setFormat(value as "csv" | "json")}
                    style={{
                      flex: 1, padding: "10px 0", borderRadius: 8,
                      border: `2px solid ${format === value ? "var(--primary)" : "var(--border-color)"}`,
                      background: format === value ? "var(--primary-light)" : "white",
                      color: format === value ? "var(--primary)" : "var(--text-secondary)",
                      fontWeight: 700, fontSize: 13, cursor: "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                      transition: "all 0.15s",
                    }}
                  >
                    <Icon size={14} /> {label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label className="label">
                <Filter size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
                Filter by Risk Tier
              </label>
              <select
                className="input"
                value={tier}
                onChange={(e) => setTier(e.target.value)}
              >
                <option value="">All Tiers</option>
                <option value="healthy">Healthy</option>
                <option value="depression_only">Depression Only</option>
                <option value="anxiety_only">Anxiety Only</option>
                <option value="comorbid">Comorbid</option>
              </select>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleExport}
              disabled={exporting}
              style={{ width: "100%", justifyContent: "center" }}
            >
              {exporting ? (
                <><span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Preparing export…</>
              ) : done ? (
                "✓ Export ready — check downloads"
              ) : (
                <><Download size={15} /> Export Dataset</>
              )}
            </button>

            {error && (
              <div style={{
                marginTop: 12, padding: "10px 14px", borderRadius: 8,
                background: "#FEF2F2", border: "1px solid #FECACA",
                display: "flex", gap: 8, alignItems: "center",
                fontSize: 13, color: "#DC2626",
              }}>
                <AlertCircle size={15} style={{ flexShrink: 0 }} />
                {error}
              </div>
            )}
          </div>

          {/* What's included */}
          <div className="card" style={{ padding: 28 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>What's included</h3>
            {[
              { label: "Anonymized sample ID", included: true },
              { label: "Collection date", included: true },
              { label: "13 bacterial taxa abundances", included: true },
              { label: "Depression probability", included: true },
              { label: "Anxiety probability", included: true },
              { label: "Risk tier classification", included: true },
              { label: "Confidence intervals (±CI)", included: true },
              { label: "Patient name / NHS ID", included: false },
              { label: "Clinician name", included: false },
              { label: "Hospital identifiers", included: false },
            ].map(({ label, included }) => (
              <div key={label} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "7px 0", borderBottom: "1px solid var(--border-light)",
                fontSize: 13,
              }}>
                <span style={{
                  width: 18, height: 18, borderRadius: "50%", flexShrink: 0,
                  background: included ? "#DCFCE7" : "#FEE2E2",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 10, fontWeight: 900,
                  color: included ? "#16A34A" : "#DC2626",
                }}>
                  {included ? "✓" : "✕"}
                </span>
                <span style={{ color: included ? "var(--text-primary)" : "var(--text-tertiary)" }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

export default function ExportPage() {
  return (
    <RoleGuard allowedRoles={["researcher", "admin"]}>
      <ExportPageContent />
    </RoleGuard>
  );
}
