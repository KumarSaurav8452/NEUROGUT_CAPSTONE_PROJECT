"use client";
import { Suspense } from "react";
import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Brain, Eye, EyeOff, CheckCircle2, AlertTriangle, Lock } from "lucide-react";

type PageState = "idle" | "loading" | "success" | "error" | "expired";

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" />
      </div>
    }>
      <AcceptInviteContent />
    </Suspense>
  );
}

function AcceptInviteContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [state, setState] = useState<PageState>(token ? "idle" : "error");
  const [errorMsg, setErrorMsg] = useState(
    token ? "" : "No invitation token found in this link. Please use the link from your invitation email."
  );

  // Password strength
  const strength = (() => {
    let s = 0;
    if (password.length >= 8) s++;
    if (/[A-Z]/.test(password)) s++;
    if (/[0-9]/.test(password)) s++;
    if (/[^A-Za-z0-9]/.test(password)) s++;
    return s; // 0–4
  })();

  const strengthLabel = ["", "Weak", "Fair", "Good", "Strong"][strength];
  const strengthColor = ["", "#EF4444", "#F59E0B", "#3B82F6", "#22C55E"][strength];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setErrorMsg("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setErrorMsg("Password must be at least 8 characters.");
      return;
    }

    setState("loading");
    setErrorMsg("");
    try {
      const tok = await api.acceptInvite(token, password);
      // Auto-login
      api.setToken(tok.access_token);
      setState("success");
      setTimeout(() => router.replace("/dashboard"), 2000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to activate account";
      if (msg.toLowerCase().includes("expired")) {
        setState("expired");
      } else {
        setState("error");
        setErrorMsg(msg);
      }
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #EFF8FA 0%, #F8FAFC 60%, #F0FDF4 100%)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "24px 16px",
    }}>
      <div style={{ width: "100%", maxWidth: 440 }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 60, height: 60, borderRadius: 18,
            background: "linear-gradient(135deg, #0047AB, #0F9D8A)",
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 12px",
          }}>
            <Brain size={32} color="white" />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: "#1E293B", margin: 0 }}>NEUROGUT</h1>
          <p style={{ fontSize: 13, color: "#64748B", margin: "4px 0 0" }}>Gut-Brain Axis Diagnostic Platform</p>
        </div>

        {/* Card */}
        <div style={{
          background: "white", borderRadius: 16, padding: 32,
          boxShadow: "0 4px 24px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)",
          border: "1px solid #E2E8F0",
        }}>
          {/* ── Success State ── */}
          {state === "success" && (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                background: "#DCFCE7", display: "flex", alignItems: "center",
                justifyContent: "center", margin: "0 auto 16px",
              }}>
                <CheckCircle2 size={36} color="#16A34A" />
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: "#1E293B" }}>
                Account Activated!
              </h2>
              <p style={{ color: "#64748B", fontSize: 14, lineHeight: 1.6 }}>
                Your password has been set. Redirecting you to the dashboard…
              </p>
            </div>
          )}

          {/* ── Expired State ── */}
          {state === "expired" && (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                background: "#FEF9C3", display: "flex", alignItems: "center",
                justifyContent: "center", margin: "0 auto 16px",
              }}>
                <AlertTriangle size={36} color="#CA8A04" />
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: "#1E293B" }}>
                Invitation Expired
              </h2>
              <p style={{ color: "#64748B", fontSize: 14, lineHeight: 1.6 }}>
                This invitation link has expired (72-hour limit). Please contact your administrator
                to resend the invitation.
              </p>
            </div>
          )}

          {/* ── Error State (no token) ── */}
          {state === "error" && !token && (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                background: "#FEE2E2", display: "flex", alignItems: "center",
                justifyContent: "center", margin: "0 auto 16px",
              }}>
                <AlertTriangle size={36} color="#DC2626" />
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: "#1E293B" }}>
                Invalid Link
              </h2>
              <p style={{ color: "#64748B", fontSize: 14, lineHeight: 1.6 }}>
                {errorMsg}
              </p>
            </div>
          )}

          {/* ── Form ── */}
          {(state === "idle" || state === "loading" || (state === "error" && token)) && (
            <>
              <div style={{ marginBottom: 24 }}>
                <h2 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 6px" }}>
                  Set Your Password
                </h2>
                <p style={{ fontSize: 13, color: "#64748B", margin: 0 }}>
                  Create a secure password to activate your NEUROGUT account.
                </p>
              </div>

              {errorMsg && (
                <div style={{
                  background: "#FEF2F2", border: "1px solid #FECACA",
                  borderRadius: 8, padding: "10px 14px", marginBottom: 16,
                  fontSize: 13, color: "#B91C1C",
                }}>
                  {errorMsg}
                </div>
              )}

              <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 6, color: "#374151" }}>
                    New Password *
                  </label>
                  <div style={{ position: "relative" }}>
                    <Lock size={15} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#94A3B8" }} />
                    <input
                      className="input"
                      type={showPw ? "text" : "password"}
                      required
                      minLength={8}
                      placeholder="Min. 8 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      style={{ paddingLeft: 36, paddingRight: 40, margin: 0 }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw((v) => !v)}
                      style={{
                        position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                        background: "none", border: "none", cursor: "pointer", color: "#94A3B8", padding: 4,
                      }}
                    >
                      {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                  {/* Strength meter */}
                  {password && (
                    <div style={{ marginTop: 6 }}>
                      <div style={{ display: "flex", gap: 3, marginBottom: 3 }}>
                        {[1, 2, 3, 4].map((n) => (
                          <div key={n} style={{
                            flex: 1, height: 3, borderRadius: 2,
                            background: n <= strength ? strengthColor : "#E2E8F0",
                            transition: "background 0.3s",
                          }} />
                        ))}
                      </div>
                      <span style={{ fontSize: 11, color: strengthColor, fontWeight: 600 }}>{strengthLabel}</span>
                    </div>
                  )}
                </div>

                <div style={{ marginBottom: 24 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 6, color: "#374151" }}>
                    Confirm Password *
                  </label>
                  <div style={{ position: "relative" }}>
                    <Lock size={15} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#94A3B8" }} />
                    <input
                      className="input"
                      type={showPw ? "text" : "password"}
                      required
                      placeholder="Repeat your password"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      style={{
                        paddingLeft: 36, margin: 0,
                        borderColor: confirm && confirm !== password ? "#EF4444" : undefined,
                      }}
                    />
                  </div>
                  {confirm && confirm !== password && (
                    <p style={{ fontSize: 11, color: "#EF4444", margin: "4px 0 0" }}>Passwords do not match</p>
                  )}
                </div>

                <button
                  className="btn btn-primary"
                  type="submit"
                  disabled={state === "loading" || !password || !confirm}
                  style={{ width: "100%", justifyContent: "center", fontSize: 15, padding: "12px" }}
                >
                  {state === "loading" ? "Activating Account…" : "Accept Invitation & Activate"}
                </button>
              </form>
            </>
          )}
        </div>

        <p style={{ textAlign: "center", fontSize: 12, color: "#94A3B8", marginTop: 20 }}>
          Already have an account?{" "}
          <a href="/login" style={{ color: "var(--primary)", textDecoration: "none", fontWeight: 600 }}>Sign in</a>
        </p>
      </div>
    </div>
  );
}
