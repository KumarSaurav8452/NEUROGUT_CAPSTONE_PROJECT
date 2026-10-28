"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { VERSION_KEY } from "@/lib/version";
import {
  LayoutDashboard, FlaskConical, Users, FileText,
  LogOut, Activity, Shield, Bell,
  BarChart3, ClipboardList, Upload, Download,
  Brain, Microscope, BookOpen, Sparkles, History,
  type LucideIcon,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: boolean;
}

interface NavSection {
  section: string;
  items: NavItem[];
}

// Clinician nav (has patient access, alerts, reports)
// ---------------------------------------------------------------------------
const CLINICIAN_NAV: NavSection[] = [
  {
    section: "Clinical",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/analysis", label: "New Analysis", icon: FlaskConical },
      { href: "/patients", label: "Patients", icon: Users },
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/alerts", label: "Alerts", icon: Bell, badge: true },
    ],
  },
  {
    section: "Analytics",
    items: [
      { href: "/benchmarks", label: "Benchmarks", icon: BarChart3 },
      { href: "/model", label: "Model Health", icon: Activity },
    ],
  },
];

// ---------------------------------------------------------------------------
// Researcher nav (batch-focused, no individual patient access)
// ---------------------------------------------------------------------------
const RESEARCHER_NAV: NavSection[] = [
  {
    section: "Research",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/analysis", label: "Batch Upload", icon: Upload },
      { href: "/export", label: "Data Export", icon: Download },
      { href: "/benchmarks", label: "Cohort Benchmarks", icon: BarChart3 },
    ],
  },
  {
    section: "System",
    items: [
      { href: "/model", label: "Model Health", icon: Activity },
      { href: "/audit", label: "Audit Log", icon: ClipboardList },
    ],
  },
];

// ---------------------------------------------------------------------------
// Admin-only nav section
// ---------------------------------------------------------------------------
const ADMIN_SECTION: NavSection = {
  section: "Admin",
  items: [
    { href: "/admin", label: "User Management", icon: Shield },
    { href: "/audit", label: "Audit Log", icon: ClipboardList },
  ],
};

// ---------------------------------------------------------------------------
// NeuroGut v2 nav (Parkinson's + Schizophrenia research results, static data)
// ---------------------------------------------------------------------------
const V2_NAV: NavSection[] = [
  {
    section: "NeuroGut v2",
    items: [
      { href: "/v2", label: "Overview", icon: Sparkles },
      { href: "/v2/predict", label: "New Prediction", icon: FlaskConical },
      { href: "/v2/history", label: "Prediction History", icon: History },
    ],
  },
  {
    section: "Research findings",
    items: [
      { href: "/v2/schizophrenia", label: "Schizophrenia", icon: Brain },
      { href: "/v2/parkinsons", label: "Parkinson's", icon: Microscope },
      { href: "/v2/methods", label: "Methods", icon: BookOpen },
    ],
  },
];


// ---------------------------------------------------------------------------
// Role badge colors
// ---------------------------------------------------------------------------
const ROLE_COLORS: Record<string, { bg: string; color: string }> = {
  admin:      { bg: "#1E3A5F", color: "#fff" },
  clinician:  { bg: "#1D4ED8", color: "#fff" },
  researcher: { bg: "#0F766E", color: "#fff" },
};

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    // Only clinicians and admins see alert counts
    if (user && user.role !== "researcher") {
      api.getAlertCount().then((c) => setAlertCount(c.unread)).catch(() => {});
      const interval = setInterval(() => {
        api.getAlertCount().then((c) => setAlertCount(c.unread)).catch(() => {});
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [user]);

  const isV2 = pathname === "/v2" || pathname?.startsWith("/v2/");

  useEffect(() => {
    try { localStorage.setItem(VERSION_KEY, isV2 ? "v2" : "classic"); } catch {}
  }, [isV2]);

  if (!user) return null;

  // Select nav items based on version, then role
  const navSections = isV2 ? V2_NAV
    : user.role === "researcher" ? RESEARCHER_NAV : CLINICIAN_NAV;

  const roleBadge = ROLE_COLORS[user.role] ?? ROLE_COLORS.clinician;

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>NEUROGUT</h1>
        <p>{isV2 ? "Parkinson's & Schizophrenia" : "Gut-Brain Diagnostics"}</p>
        <div className="version-toggle" role="tablist" aria-label="Website version">
          <Link href="/dashboard" role="tab" aria-selected={!isV2} className={!isV2 ? "on" : ""}>Classic</Link>
          <Link href="/v2" role="tab" aria-selected={isV2} className={isV2 ? "on v2" : ""}>NeuroGut v2</Link>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navSections.map((section) => (
          <div className="nav-section" key={section.section}>
            <div className="nav-section-title">{section.section}</div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href !== "/v2" && pathname?.startsWith(item.href + "/"));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-link ${isActive ? "active" : ""}`}
                >
                  <Icon />
                  {item.label}
                  {item.badge === true && alertCount > 0 && (
                    <span style={{
                      marginLeft: "auto", background: "#EF4444", color: "white",
                      fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 10,
                      minWidth: 18, textAlign: "center", lineHeight: "16px",
                    }}>
                      {alertCount > 99 ? "99+" : alertCount}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}

        {/* Admin-only section */}
        {user.role === "admin" && !isV2 && (
          <div className="nav-section">
            <div className="nav-section-title">{ADMIN_SECTION.section}</div>
            {ADMIN_SECTION.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href !== "/v2" && pathname?.startsWith(item.href + "/"));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-link ${isActive ? "active" : ""}`}
                >
                  <Icon />
                  {item.label}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      <div style={{ padding: "16px 12px", borderTop: "1px solid var(--border-color)" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: "10px",
          marginBottom: "12px", padding: "0 8px",
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            background: "var(--primary-light)", display: "flex",
            alignItems: "center", justifyContent: "center",
            color: "var(--primary)", fontWeight: 700, fontSize: 14,
          }}>
            {user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {user.full_name}
            </div>
            <div style={{ marginTop: 2 }}>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: "1px 7px",
                borderRadius: 20, letterSpacing: 0.5, textTransform: "uppercase",
                background: roleBadge.bg, color: roleBadge.color,
              }}>
                {user.role}
              </span>
            </div>
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={logout} style={{ width: "100%" }}>
          <LogOut size={14} /> Sign Out
        </button>
      </div>
    </aside>
  );
}
