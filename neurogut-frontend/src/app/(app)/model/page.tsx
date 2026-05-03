"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ModelHealth } from "@/lib/types";
import { Activity, Cpu, Zap, Database, CheckCircle } from "lucide-react";

export default function ModelPage() {
  const [health, setHealth] = useState<ModelHealth | null>(null);

  useEffect(() => {
    const f = () => api.getModelHealth().then(setHealth).catch(() => {});
    f();
    const i = setInterval(f, 5000);
    return () => clearInterval(i);
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Model Health</h1>
        <p>GutMicrobiomeStacker status (auto-refreshes every 5s)</p>
      </div>
      <div className="page-body stagger-children">
        <div className="card" style={{
          padding: 24, display: "flex", alignItems: "center", gap: 16, marginBottom: 24,
          borderLeft: `4px solid ${health?.model_loaded ? "#22C55E" : "#EF4444"}`,
        }}>
          <CheckCircle size={32} color={health?.model_loaded ? "#22C55E" : "#EF4444"} />
          <div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>
              {health?.model_loaded ? "Model Online" : "Model Offline"}
            </div>
            <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>
              GutMicrobiomeStacker is loaded and ready for predictions
            </div>
          </div>
        </div>

        <div className="stats-grid">
          {[
            { icon: Cpu, label: "Version", value: health?.model_version ?? "--", bg: "var(--primary-light)", color: "var(--primary)" },
            { icon: Database, label: "Features", value: String(health?.feature_count ?? 0), bg: "#EFF6FF", color: "#3B82F6" },
            { icon: Activity, label: "Predictions", value: String(health?.prediction_count ?? 0), bg: "#F0FDF4", color: "#22C55E" },
            { icon: Zap, label: "Avg Latency", value: health?.avg_latency_ms ? `${Math.round(health.avg_latency_ms)}ms` : "--", bg: "#FFFBEB", color: "#F59E0B" },
          ].map((s) => (
            <div className="card stat-card" key={s.label}>
              <div className="stat-icon" style={{ background: s.bg }}>
                <s.icon size={20} color={s.color} />
              </div>
              <div className="stat-value">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Architecture</h3>
          {[
            { l: "Base 1", v: "MultiOutputClassifier(RandomForest, n=100)", c: "#006D77" },
            { l: "Base 2", v: "ClassifierChain(XGBoost, Depression->Anxiety)", c: "#3B82F6" },
            { l: "Meta", v: "MultiOutputClassifier(LogisticRegression)", c: "#A855F7" },
          ].map((i) => (
            <div key={i.l} style={{ display: "flex", gap: 16, padding: 12, background: "var(--bg-secondary)", borderRadius: 8, borderLeft: `3px solid ${i.c}`, marginBottom: 8 }}>
              <span style={{ minWidth: 60, fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>{i.l}</span>
              <span style={{ fontSize: 13, fontFamily: "'JetBrains Mono', monospace" }}>{i.v}</span>
            </div>
          ))}
        </div>

        <div className="card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>CV Metrics (5-Fold)</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            {[
              { l: "Dep AUC", v: "0.945", c: "#006D77" },
              { l: "Anx AUC", v: "0.893", c: "#3B82F6" },
              { l: "Dep F1", v: "0.933", c: "#22C55E" },
              { l: "Anx F1", v: "0.862", c: "#F59E0B" },
              { l: "Hamming", v: "0.086", c: "#EF4444" },
            ].map((m) => (
              <div key={m.l} style={{ padding: 16, background: "var(--bg-secondary)", borderRadius: 8, textAlign: "center" }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: m.c }}>{m.v}</div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>{m.l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
