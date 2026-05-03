"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  LayoutDashboard, FlaskConical, Users, FileText,
  Settings, LogOut, Activity, Shield,
} from "lucide-react";

const NAV_ITEMS = [
  { section: "Clinical", items: [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/analysis", label: "New Analysis", icon: FlaskConical },
    { href: "/patients", label: "Patients", icon: Users },
    { href: "/reports", label: "Reports", icon: FileText },
  ]},
  { section: "System", items: [
    { href: "/model", label: "Model Health", icon: Activity },
  ]},
];

const ADMIN_ITEMS = [
  { href: "/admin", label: "User Management", icon: Shield },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>NEUROGUT</h1>
        <p>Gut-Brain Diagnostics</p>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((section) => (
          <div className="nav-section" key={section.section}>
            <div className="nav-section-title">{section.section}</div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
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
        ))}

        {user.role === "admin" && (
          <div className="nav-section">
            <div className="nav-section-title">Admin</div>
            {ADMIN_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
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

      <div style={{
        padding: "16px 12px",
        borderTop: "1px solid var(--border-color)",
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          marginBottom: "12px",
          padding: "0 8px",
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            background: "var(--primary-light)", display: "flex",
            alignItems: "center", justifyContent: "center",
            color: "var(--primary)", fontWeight: 700, fontSize: 14,
          }}>
            {user.full_name.split(" ").map(n => n[0]).join("").slice(0, 2)}
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
              {user.full_name}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary)", textTransform: "capitalize" }}>
              {user.role}
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
