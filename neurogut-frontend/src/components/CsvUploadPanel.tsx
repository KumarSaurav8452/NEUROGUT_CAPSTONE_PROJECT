"use client";
import { useState, useCallback, useRef } from "react";
import Papa from "papaparse";
import { api } from "@/lib/api";
import { RISK_CONFIG, TAXA_NAMES, TAXA_DISPLAY } from "@/lib/types";
import type { CsvUploadResult, CsvPredictionRow, RiskTier } from "@/lib/types";
import {
  Upload, FileText, CheckCircle, XCircle, AlertTriangle,
  Download, Trash2, BarChart3, Brain, Heart,
} from "lucide-react";

interface ParsedRow {
  rowIndex: number;
  values: Record<string, number>;
  valid: boolean;
  error?: string;
}

const EXPECTED_HEADERS = TAXA_NAMES.map((t) => t.toLowerCase());

export default function CsvUploadPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [parsedRows, setParsedRows] = useState<ParsedRow[]>([]);
  const [parseError, setParseError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<CsvUploadResult | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    setFile(f);
    setResults(null);
    setParseError("");

    if (!f.name.toLowerCase().endsWith(".csv")) {
      setParseError("File must be a .csv file");
      setParsedRows([]);
      return;
    }

    Papa.parse(f, {
      header: true,
      skipEmptyLines: true,
      complete: (result) => {
        if (!result.meta.fields || result.meta.fields.length === 0) {
          setParseError("CSV has no headers");
          setParsedRows([]);
          return;
        }

        // Validate headers
        const headers = result.meta.fields.map((h: string) => h.trim().toLowerCase());
        const missing = EXPECTED_HEADERS.filter((h) => !headers.includes(h));
        if (missing.length > 0) {
          setParseError(`Missing columns: ${missing.map((m) => TAXA_DISPLAY[m] || m).join(", ")}`);
          setParsedRows([]);
          return;
        }

        // Parse rows
        const rows: ParsedRow[] = [];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (result.data as any[]).forEach((row: Record<string, string>, i: number) => {
          const values: Record<string, number> = {};
          let valid = true;
          let error = "";

          for (const taxon of EXPECTED_HEADERS) {
            // Case-insensitive key match
            const key = Object.keys(row).find((k) => k.trim().toLowerCase() === taxon);
            const val = key ? row[key]?.trim() : "";
            if (!val || val === "") {
              valid = false;
              error = `Missing value for ${TAXA_DISPLAY[taxon] || taxon}`;
              break;
            }
            const num = parseFloat(val);
            if (isNaN(num)) {
              valid = false;
              error = `Invalid number for ${TAXA_DISPLAY[taxon] || taxon}: "${val}"`;
              break;
            }
            values[taxon] = num;
          }
          rows.push({ rowIndex: i + 1, values, valid, error });
        });

        setParsedRows(rows);
        if (rows.length === 0) {
          setParseError("CSV contains no data rows");
        }
      },
      error: (err) => {
        setParseError(`Parse error: ${err.message}`);
        setParsedRows([]);
      },
    });
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0]);
    },
    [handleFile]
  );

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setParseError("");
    try {
      const result = await api.predictCsv(file);
      setResults(result);
    } catch (err: unknown) {
      setParseError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadResults = () => {
    if (!results) return;
    const headers = [
      "Row", "Risk Tier", "Depression %", "Depression CI", "Anxiety %", "Anxiety CI", "Model",
    ];
    const csvRows = results.predictions.map((p) => [
      p.row,
      p.risk_tier,
      (p.depression_prob * 100).toFixed(1),
      p.depression_ci_low != null
        ? `${(p.depression_ci_low * 100).toFixed(1)}-${((p.depression_ci_high ?? 0) * 100).toFixed(1)}`
        : "N/A",
      (p.anxiety_prob * 100).toFixed(1),
      p.anxiety_ci_low != null
        ? `${(p.anxiety_ci_low * 100).toFixed(1)}-${((p.anxiety_ci_high ?? 0) * 100).toFixed(1)}`
        : "N/A",
      p.model_version,
    ]);
    const csv = [headers.join(","), ...csvRows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `neurogut_results_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClear = () => {
    setFile(null);
    setParsedRows([]);
    setResults(null);
    setParseError("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const validCount = parsedRows.filter((r) => r.valid).length;
  const invalidCount = parsedRows.filter((r) => !r.valid).length;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* Drop zone */}
      {!results && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          style={{
            border: `2px dashed ${dragActive ? "var(--primary)" : "var(--border-color)"}`,
            borderRadius: 12, padding: "40px 20px", textAlign: "center",
            cursor: "pointer", transition: "all 0.2s",
            background: dragActive ? "var(--primary-light)" : "var(--bg-secondary)",
          }}
        >
          <input
            ref={inputRef} type="file" accept=".csv"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          <Upload size={36} color={dragActive ? "var(--primary)" : "var(--text-tertiary)"} style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
            {file ? file.name : "Drop CSV file here or click to browse"}
          </p>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            13 taxa columns required • Supports up to 500 rows
          </p>
          <a
            href={api.getCsvTemplateUrl()}
            onClick={(e) => e.stopPropagation()}
            style={{ fontSize: 12, color: "var(--primary)", textDecoration: "underline", marginTop: 8, display: "inline-block" }}
          >
            <Download size={12} /> Download CSV Template
          </a>
        </div>
      )}

      {/* Parse error */}
      {parseError && (
        <div style={{ padding: "10px 14px", background: "#FEF2F2", border: "1px solid #FCA5A5", borderRadius: 8, color: "#DC2626", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
          <AlertTriangle size={16} /> {parseError}
        </div>
      )}

      {/* Preview table */}
      {parsedRows.length > 0 && !results && (
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0 }}>
                <FileText size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
                Preview — {parsedRows.length} rows
              </h3>
              <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>
                <span style={{ color: "#22C55E" }}>✓ {validCount} valid</span>
                {invalidCount > 0 && <span style={{ color: "#EF4444", marginLeft: 8 }}>✗ {invalidCount} invalid</span>}
              </p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={handleClear}>
                <Trash2 size={12} /> Clear
              </button>
              <button className="btn btn-primary" style={{ fontSize: 12 }} onClick={handleUpload}
                disabled={validCount === 0 || uploading}>
                {uploading ? <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                  : <><BarChart3 size={12} /> Analyze {validCount} Rows</>}
              </button>
            </div>
          </div>

          <div style={{ overflowX: "auto", maxHeight: 300 }}>
            <table className="data-table" style={{ fontSize: 11 }}>
              <thead>
                <tr>
                  <th style={{ width: 40 }}>Row</th>
                  <th style={{ width: 40 }}>✓</th>
                  {TAXA_NAMES.slice(0, 6).map((t) => (
                    <th key={t} style={{ fontSize: 10 }}>{TAXA_DISPLAY[t]?.slice(0, 6)}</th>
                  ))}
                  <th>...</th>
                </tr>
              </thead>
              <tbody>
                {parsedRows.slice(0, 20).map((row) => (
                  <tr key={row.rowIndex} style={{ opacity: row.valid ? 1 : 0.5 }}>
                    <td>{row.rowIndex}</td>
                    <td>{row.valid ? <CheckCircle size={12} color="#22C55E" /> : <XCircle size={12} color="#EF4444" />}</td>
                    {TAXA_NAMES.slice(0, 6).map((t) => (
                      <td key={t}>{row.values[t]?.toFixed(2) ?? "—"}</td>
                    ))}
                    <td style={{ fontSize: 10, color: "var(--text-tertiary)" }}>
                      {row.valid ? `+${TAXA_NAMES.length - 6} cols` : row.error}
                    </td>
                  </tr>
                ))}
                {parsedRows.length > 20 && (
                  <tr><td colSpan={9} style={{ textAlign: "center", color: "var(--text-tertiary)" }}>
                    ... and {parsedRows.length - 20} more rows
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="animate-fade-in" style={{ display: "grid", gap: 16 }}>
          {/* Summary */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
            <div className="card" style={{ padding: 16, textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: "var(--primary)" }}>{results.total_rows}</div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>Total Rows</div>
            </div>
            <div className="card" style={{ padding: 16, textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#22C55E" }}>{results.successful}</div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>Successful</div>
            </div>
            <div className="card" style={{ padding: 16, textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#EF4444" }}>{results.failed}</div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>Failed</div>
            </div>
            <div className="card" style={{ padding: 16, textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#F59E0B" }}>
                {results.predictions.filter((p) => p.risk_tier === "comorbid").length}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>High Risk</div>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" style={{ fontSize: 12 }} onClick={handleDownloadResults}>
              <Download size={14} /> Download Results CSV
            </button>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={handleClear}>
              <Upload size={14} /> Upload Another
            </button>
          </div>

          {/* Results table */}
          <div className="card" style={{ overflow: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Risk Tier</th>
                  <th><Brain size={12} /> Depression</th>
                  <th>95% CI</th>
                  <th><Heart size={12} /> Anxiety</th>
                  <th>95% CI</th>
                </tr>
              </thead>
              <tbody>
                {results.predictions.map((p) => {
                  const rc = RISK_CONFIG[p.risk_tier as RiskTier] || RISK_CONFIG.healthy;
                  return (
                    <tr key={p.row}>
                      <td style={{ fontWeight: 600 }}>{p.row}</td>
                      <td>
                        <span className={`badge ${rc.badge}`}>{rc.label}</span>
                      </td>
                      <td style={{ fontWeight: 600, color: p.depression_label ? "#F59E0B" : "#22C55E" }}>
                        {(p.depression_prob * 100).toFixed(1)}%
                      </td>
                      <td style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                        {p.depression_ci_low != null
                          ? `${(p.depression_ci_low * 100).toFixed(1)}–${((p.depression_ci_high ?? 0) * 100).toFixed(1)}%`
                          : "—"}
                      </td>
                      <td style={{ fontWeight: 600, color: p.anxiety_label ? "#F59E0B" : "#22C55E" }}>
                        {(p.anxiety_prob * 100).toFixed(1)}%
                      </td>
                      <td style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                        {p.anxiety_ci_low != null
                          ? `${(p.anxiety_ci_low * 100).toFixed(1)}–${((p.anxiety_ci_high ?? 0) * 100).toFixed(1)}%`
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Errors */}
          {results.errors.length > 0 && (
            <div className="card" style={{ padding: 16, borderLeft: "4px solid #EF4444" }}>
              <h4 style={{ fontSize: 13, fontWeight: 700, color: "#EF4444", marginBottom: 8 }}>
                <AlertTriangle size={14} /> {results.errors.length} Failed Rows
              </h4>
              {results.errors.map((e) => (
                <div key={e.row} style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
                  Row {e.row}: {e.error}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
