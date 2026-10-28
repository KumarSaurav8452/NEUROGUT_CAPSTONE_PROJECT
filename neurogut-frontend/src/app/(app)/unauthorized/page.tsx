"use client";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ShieldX, ArrowLeft, Home } from "lucide-react";

export default function UnauthorizedPage() {
  const router = useRouter();
  const { user } = useAuth();

  const roleLabel = user?.role
    ? user.role.charAt(0).toUpperCase() + user.role.slice(1)
    : "Unknown";

  return (
    <>
      <div className="page-header">
        <h1>Access Denied</h1>
        <p>You do not have permission to view this page</p>
      </div>

      <div className="page-body">
        <div className="card" style={{
          padding: "56px 40px", textAlign: "center",
          maxWidth: 520, margin: "0 auto",
        }}>
          {/* Icon */}
          <div style={{
            width: 80, height: 80, borderRadius: "50%",
            background: "#FEF2F2", display: "flex", alignItems: "center",
            justifyContent: "center", margin: "0 auto 24px",
          }}>
            <ShieldX size={40} color="#EF4444" />
          </div>

          <h2 style={{ fontSize: 22, fontWeight: 700, margin: "0 0 12px", color: "var(--text-primary)" }}>
            403 — Unauthorized
          </h2>

          <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.7, margin: "0 0 8px" }}>
            Your account role (<strong>{roleLabel}</strong>) does not have access to this section.
          </p>
          <p style={{ fontSize: 13, color: "var(--text-tertiary)", lineHeight: 1.6, margin: "0 0 32px" }}>
            If you believe this is a mistake, please contact your hospital administrator to
            review your permissions.
          </p>

          {/* Actions */}
          <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
            <button
              className="btn btn-secondary"
              onClick={() => router.back()}
            >
              <ArrowLeft size={15} /> Go Back
            </button>
            <button
              className="btn btn-primary"
              onClick={() => router.replace("/dashboard")}
            >
              <Home size={15} /> Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
