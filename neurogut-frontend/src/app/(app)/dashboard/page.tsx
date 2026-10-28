"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { RISK_CONFIG } from "@/lib/types";
import type { ModelHealth, Patient, Report, Alert, CohortBenchmark } from "@/lib/types";
import {
  Activity, Users, FileText, FlaskConical, TrendingUp,
  Brain, Heart, AlertTriangle, Upload, Download, BarChart3,
  Clock, CheckCircle2, Package,
} from "lucide-react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Clinician Dashboard
// ---------------------------------------------------------------------------
function ClinicianDashboard() {
  const { user } = useAuth();
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [totalPatients, setTotalPatients] = useState(0);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    api.getModelHealth().then(setHealth).catch(() => {});
    api.listPatients(1, 5).then((r) => {
      setPatients(r.patients);
      setTotalPatients(r.total);
    }).catch(() => {});
    api.listReports().then(setReports).catch(() => {});
    api.getAlertCount().then((c) => setAlertCount(c.unread)).catch(() => {});
    api.listAlerts("unread", 1).then(setAlerts).catch(() => {});
  }, []);

  // Approx "predictions this month" from reports length (closest proxy without dedicated endpoint)
  const predictionsThisMonth = health?.prediction_count ?? 0;
  const highRiskCount = alerts.length;

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Welcome back, {user?.full_name} — <span style={{ textTransform: "capitalize", color: "var(--primary)" }}>Clinician</span></p>
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
            <div className="stat-value">{predictionsThisMonth}</div>
            <div className="stat-label">Predictions Run</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#FEF2F2" }}>
              <AlertTriangle size={20} color="#EF4444" />
            </div>
            <div className="stat-value">{alertCount}</div>
            <div className="stat-label">High Risk Alerts</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#FDF4FF" }}>
              <FileText size={20} color="#A855F7" />
            </div>
            <div className="stat-value">{reports.length}</div>
            <div className="stat-label">Reports Generated</div>
          </div>
        </div>

        {/* Quick Actions + Model Status */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
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
                <FileText size={16} /> Download Reports
              </Link>
            </div>
          </div>

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
                <span style={{ fontSize: 13, fontWeight: 600 }}>{health?.feature_count ?? 0} bacterial taxa</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0" }}>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Avg Latency</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  {health?.avg_latency_ms ? `${Math.round(health.avg_latency_ms)}ms` : "--"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Patients + Unread Alerts */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
          {/* Recent Patients */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Recent Patients</h3>
              <Link href="/patients" style={{ fontSize: 13, color: "var(--primary)", textDecoration: "none" }}>View all →</Link>
            </div>
            {patients.length === 0 ? (
              <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>No patients yet.</p>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {patients.map((p) => (
                  <Link key={p.id} href={`/patients/${p.id}`} style={{
                    display: "flex", alignItems: "center", gap: 10, padding: "8px 0",
                    borderBottom: "1px solid var(--border-light)", textDecoration: "none", color: "inherit",
                  }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: "50%", background: "var(--primary-light)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 12, fontWeight: 700, color: "var(--primary)",
                    }}>
                      {p.patient_code.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{p.patient_code}</div>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                        {p.age ? `${p.age}y` : "Age N/A"} · {p.sex}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Unread Alerts */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: 6 }}>
                <AlertTriangle size={16} color="#EF4444" />
                Unread Alerts
                {alertCount > 0 && (
                  <span style={{
                    background: "#EF4444", color: "white", fontSize: 10, fontWeight: 700,
                    padding: "1px 7px", borderRadius: 20, marginLeft: 4,
                  }}>{alertCount}</span>
                )}
              </h3>
              <Link href="/alerts" style={{ fontSize: 13, color: "var(--primary)", textDecoration: "none" }}>View all →</Link>
            </div>
            {alerts.length === 0 ? (
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <CheckCircle2 size={32} color="#22C55E" style={{ marginBottom: 8, opacity: 0.7 }} />
                <p style={{ color: "var(--text-tertiary)", fontSize: 13, margin: 0 }}>No unread alerts</p>
              </div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {alerts.slice(0, 5).map((a) => (
                  <div key={a.id} style={{
                    padding: "10px 12px", borderRadius: 8,
                    background: "#FEF2F2", border: "1px solid #FECACA",
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#EF4444", marginBottom: 2 }}>
                      {a.triggered_by_rule.replace(/_/g, " ").toUpperCase()}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      Patient {a.patient_id?.slice(0, 8)}…
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* About Card */}
        <div className="card" style={{ padding: 24, background: "linear-gradient(135deg, var(--primary-light), white)" }}>
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16,
              background: "linear-gradient(135deg, #0047AB, #0F9D8A)",
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
                to predict Depression and Anxiety risk from 13 bacterial taxa. Achieves
                <strong> 94.5% Depression AUC</strong> and <strong>89.3% Anxiety AUC</strong>.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Researcher Dashboard
// ---------------------------------------------------------------------------
function ResearcherDashboard() {
  const { user } = useAuth();
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [benchmarks, setBenchmarks] = useState<CohortBenchmark[]>([]);

  useEffect(() => {
    api.getModelHealth().then(setHealth).catch(() => {});
    api.getBenchmarks().then(setBenchmarks).catch(() => {});
  }, []);

  // Aggregate cohort distribution across benchmarks
  const tierCounts: Record<string, number> = {};
  benchmarks.forEach((b) => {
    tierCounts[b.risk_tier] = (tierCounts[b.risk_tier] || 0) + b.sample_count;
  });
  const totalSamples = Object.values(tierCounts).reduce((a, b) => a + b, 0);

  const tierLabels: Record<string, { label: string; color: string }> = {
    healthy:         { label: "Healthy", color: "#22C55E" },
    depression_only: { label: "Depression", color: "#F59E0B" },
    anxiety_only:    { label: "Anxiety", color: "#F59E0B" },
    comorbid:        { label: "Comorbid", color: "#EF4444" },
  };

  return (
    <>
      <div className="page-header">
        <h1>Research Dashboard</h1>
        <p>Welcome back, {user?.full_name} — <span style={{ textTransform: "capitalize", color: "#0F766E" }}>Researcher</span></p>
      </div>

      <div className="page-body stagger-children">
        {/* Stats Grid */}
        <div className="stats-grid">
          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#F0FDFA" }}>
              <Upload size={20} color="#0F766E" />
            </div>
            <div className="stat-value">{health?.prediction_count ?? 0}</div>
            <div className="stat-label">Total Samples Processed</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#EFF6FF" }}>
              <Package size={20} color="#3B82F6" />
            </div>
            <div className="stat-value">{benchmarks.length > 0 ? Object.keys(tierCounts).length : 0}</div>
            <div className="stat-label">Cohort Tiers Tracked</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#FDF4FF" }}>
              <Download size={20} color="#A855F7" />
            </div>
            <div className="stat-value">{totalSamples}</div>
            <div className="stat-label">Benchmark Samples</div>
          </div>

          <div className="card stat-card">
            <div className="stat-icon" style={{ background: "#FFF7ED" }}>
              <Activity size={20} color="#F97316" />
            </div>
            <div className="stat-value">
              {health?.avg_latency_ms ? `${Math.round(health.avg_latency_ms)}ms` : "--"}
            </div>
            <div className="stat-label">Avg Processing Time</div>
          </div>
        </div>

        {/* Quick Actions + Cohort Summary */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
          <div className="card" style={{ padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, color: "var(--text-primary)" }}>
              Quick Actions
            </h3>
            <div style={{ display: "grid", gap: 10 }}>
              <Link href="/analysis" className="btn btn-primary" style={{ justifyContent: "flex-start", background: "#0F766E" }}>
                <Upload size={16} /> New Batch Upload
              </Link>
              <Link href="/benchmarks" className="btn btn-secondary" style={{ justifyContent: "flex-start" }}>
                <BarChart3 size={16} /> View Cohort Benchmarks
              </Link>
              <Link href="/export" className="btn btn-secondary" style={{ justifyContent: "flex-start" }}>
                <Download size={16} /> Export Data
              </Link>
            </div>
          </div>

          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
              <BarChart3 size={18} color="#0F766E" />
              <h3 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                Cohort Distribution
              </h3>
            </div>
            {totalSamples === 0 ? (
              <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>No benchmark data yet.</p>
            ) : (
              <div style={{ display: "grid", gap: 12 }}>
                {Object.entries(tierCounts).map(([tier, count]) => {
                  const cfg = tierLabels[tier] ?? { label: tier, color: "#64748B" };
                  const pct = Math.round((count / totalSamples) * 100);
                  return (
                    <div key={tier}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>{cfg.label}</span>
                        <span style={{ fontSize: 13, fontWeight: 700 }}>{pct}% <span style={{ fontWeight: 400, color: "var(--text-tertiary)" }}>({count})</span></span>
                      </div>
                      <div style={{ height: 6, background: "var(--border-light)", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${pct}%`, background: cfg.color, borderRadius: 4, transition: "width 0.6s ease" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Model Info */}
        <div className="card" style={{ padding: 24, background: "linear-gradient(135deg, #F0FDFA, white)" }}>
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16,
              background: "linear-gradient(135deg, #0F766E, #14B8A6)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <Brain size={28} color="white" />
            </div>
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 8px 0" }}>
                Model v{health?.model_version ?? "..."} · Research Mode
              </h3>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>
                Stacked ensemble (RF + XGB + LR) — {health?.feature_count ?? 13} bacterial taxa.
                Batch CSV uploads are anonymized automatically. Individual patient identifiers are not
                accessible in Researcher mode per data governance policy.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Admin Dashboard — reuses Clinician view + adds user count card
// ---------------------------------------------------------------------------
function AdminDashboard() {
  return <ClinicianDashboard />;
}

// ---------------------------------------------------------------------------
// Role-dispatching entry point
// ---------------------------------------------------------------------------
export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  if (user.role === "researcher") return <ResearcherDashboard />;
  return <ClinicianDashboard />;  // clinician + admin
}
