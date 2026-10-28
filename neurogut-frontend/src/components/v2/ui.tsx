"use client";
// Shared building blocks for the NeuroGut v2 pages (static research data, see PRD_Website_v2.md).
import dynamic from "next/dynamic";
import type { ReactNode } from "react";

const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center" }}><div className="spinner" /></div>,
});

export const COBALT = "#0047AB";
export const TEAL = "#0F9D8A";
export const SERIES = [COBALT, TEAL, "#6C9BD8", "#7FD1C4", "#94A3B8"];

export const fmt = (v: number | null | undefined, d = 3) => (v == null ? "–" : v.toFixed(d));
export const studyLabel = (s: string) => s.replace(/_SCZ$/, "").replace(/_/g, " ");

export function Header({ title, sub, icon }: { title: string; sub: string; icon?: ReactNode }) {
  return (
    <div className="page-header">
      <h1>{icon}{title}</h1>
      <p>{sub}</p>
    </div>
  );
}

export function Metric({ k, v, s, teal }: { k: string; v: string; s?: string; teal?: boolean }) {
  return (
    <div className="card v2-metric">
      <div className="k">{k}</div>
      <div className={`v ${teal ? "teal" : ""}`}>{v}</div>
      {s && <div className="s">{s}</div>}
    </div>
  );
}

export function Section({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <div className="card v2-section">
      <h3>{title}</h3>
      {sub && <p className="sub">{sub}</p>}
      {children}
    </div>
  );
}

export function Table({ cols, rows }: { cols: string[]; rows: (string | number | ReactNode)[][] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data-table">
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

type Bar = { name: string; x: string[]; y: (number | null)[]; color?: string | string[]; error?: (number | null)[] };

export function Bars({ series, height = 320, yTitle = "ROC-AUC", yRange, horizontal, refLine }: {
  series: Bar[]; height?: number; yTitle?: string; yRange?: [number, number]; horizontal?: boolean; refLine?: number;
}) {
  return (
    <Plot
      data={series.map((s, i) => ({
        type: "bar" as const, name: s.name, orientation: horizontal ? ("h" as const) : ("v" as const),
        x: horizontal ? s.y : s.x, y: horizontal ? s.x : s.y,
        marker: { color: s.color ?? SERIES[i % SERIES.length] },
        text: s.y.map((v) => (v == null ? "" : v.toFixed(2))), textposition: "outside" as const,
        ...(s.error ? { error_y: { type: "data" as const, array: s.error.map((e) => e ?? 0), color: "#94A3B8", thickness: 1.2 } } : {}),
      }))}
      layout={{
        height, barmode: "group", margin: { t: 16, b: horizontal ? 40 : 90, l: horizontal ? 10 : 50, r: 30 },
        paper_bgcolor: "transparent", plot_bgcolor: "transparent", font: { family: "Inter", size: 11, color: "#0F1B2D" },
        legend: { orientation: "h", y: -0.25 }, showlegend: series.length > 1,
        [horizontal ? "xaxis" : "yaxis"]: { title: { text: yTitle }, range: yRange, gridcolor: "#E3E8F0", zeroline: false },
        [horizontal ? "yaxis" : "xaxis"]: { automargin: true, autorange: horizontal ? ("reversed" as const) : true },
        shapes: refLine == null ? [] : [{
          type: "line", xref: horizontal ? "x" : "paper", yref: horizontal ? "paper" : "y",
          x0: horizontal ? refLine : 0, x1: horizontal ? refLine : 1, y0: horizontal ? 0 : refLine, y1: horizontal ? 1 : refLine,
          line: { color: "#94A3B8", dash: "dot", width: 1 },
        }],
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%", height }}
    />
  );
}

export function Foot({ source, generated }: { source: string; generated: string }) {
  return <p className="v2-foot">Data: <code>{source}</code> · generated {generated} by <code>scripts/export_v2_data.py</code></p>;
}
