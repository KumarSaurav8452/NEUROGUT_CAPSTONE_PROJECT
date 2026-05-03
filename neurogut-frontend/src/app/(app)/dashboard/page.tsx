"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { RISK_CONFIG } from "@/lib/types";
import type { ModelHealth, Patient, Report } from "@/lib/types";
import {
  Activity, Users, FileText, FlaskConical, TrendingUp,
  Brain, Heart, AlertTriangle,
} from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [totalPatients, setTotalPatients] = useState(0);

  useEffect(() => {
    api.getModelHealth().then(setHealth).catch(() => {});
    api.listPatients(1, 5).then((r) => {
      setPatients(r.patients);
      setTotalPatients(r.total);
    }).catch(() => {});
    api.listReports().then(setReports).catch(() => {});
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Welcome back, {user?.full_name}</p>
      </div>

      <div className="page-body stagger-children">
        {/* Stats Grid */}
        <div className="stats-grid">
          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "var(--primary-light)" }}>
              <Users size={20} color="var(--primary)" />
            </div>
            <div className="stat-value">{totalPatients}</div>
            <div className="stat-label">Total Patients</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#EFF6FF" }}>
              <FlaskConical size={20} color="#3B82F6" />
            </div>
            <div className="stat-value">{health?.prediction_count ?? 0}</div>
            <div className="stat-label">Predictions Run</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#F0FDF4" }}>
              <TrendingUp size={20} color="#22C55E" />
            </div>
            <div className="stat-value">
              {health?.avg_latency_ms ? `${Math.round(health.avg_latency_ms)}ms` : "--"}
            </div>
            <div className="stat-label">Avg Latency</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#FDF4FF" }}>
              <FileText size={20} color="#A855F7" />
            </div>
            <div className="stat-value">{reports.length}</div>
            <div className="stat-label">Reports Generated</div>
          </div>
        </div>

        {/* Quick Actions + Model Status Row */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
          {/* Quick Actions */}
          <div className="card" style={{ padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, color: "var(--text-primary)" }}>
              Quick Actions
            </h3>
            <div style={{ display: "grid", gap: 10 }}>
              <Link href="/analysis" className="btn btn-primary" style={{ justifyContent: "flex-start" }}>
                <FlaskConical size={16} /> New Microbiome Analysis
              </Link>
              <Link href="/patients" className="btn btn-secondary" style={{ justifyContent: "flex-start" }}>
                <Users size={16} /> View Patients
              </Link>
              <Link href="/reports" className="btn btn-secondary" style={{ justifyContent: "flex-start" }}>
                <FileText size={16} /> View Reports
              </Link>
            </div>
          </div>

          {/* Model Health */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
              <Activity size={18} color="var(--primary)" />
              <h3 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                Model Status
              </h3>
              {health?.model_loaded && (
                <span className="badge badge-healthy" style={{ marginLeft: "auto" }}>Online</span>
              )}
            </div>

            <div style={{ display: "grid", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border-light)" }}>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Version</span>
                <span style={{ fontSize: 13, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                  {health?.model_version ?? "--"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border-light)" }}>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Features</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  {health?.feature_count ?? 0} bacterial taxa
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0" }}>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Architecture</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>RF + XGB Chain + LR Meta</span>
              </div>
            </div>
          </div>
        </div>

        {/* About Card */}
        <div className="card" style={{ padding: 24, background: "linear-gradient(135deg, var(--primary-light), white)" }}>
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16,
              background: "linear-gradient(135deg, #006D77, #00A3B5)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <Brain size={28} color="white" />
            </div>
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 8px 0" }}>
                Gut-Brain Axis Analysis
              </h3>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>
                NEUROGUT uses a stacked ensemble (RandomForest + XGBoost ClassifierChain + Logistic Regression)
                to predict Depression and Anxiety risk from 13 bacterial taxa. The model achieves
                <strong> 94.5% Depression AUC</strong> and <strong>89.3% Anxiety AUC</strong> on
                cross-validation, with consensus biomarkers Corynebacterium and Raoultella.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
