"use client";
import { homeRoute } from "@/lib/version";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { FlaskConical, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push(homeRoute());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      {/* Floating particles */}
      <div style={{
        position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none",
      }}>
        {[...Array(6)].map((_, i) => (
          <div key={i} style={{
            position: "absolute",
            width: 200 + i * 60,
            height: 200 + i * 60,
            borderRadius: "50%",
            background: `rgba(255,255,255,${0.03 + i * 0.01})`,
            top: `${10 + i * 15}%`,
            left: `${-5 + i * 18}%`,
            animation: `float${i} ${15 + i * 3}s ease-in-out infinite`,
          }} />
        ))}
      </div>

      <div className="login-card animate-fade-in" style={{ position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: "linear-gradient(135deg, #0047AB, #0F9D8A)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <FlaskConical size={22} color="white" />
          </div>
          <h1>NEUROGUT</h1>
        </div>
        <p className="login-subtitle">Gut-Brain Axis Diagnostic Platform</p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 20 }}>
            <label className="label" htmlFor="email">Email Address</label>
            <input
              id="email"
              className="input"
              type="email"
              placeholder="clinician@neurogut.demo"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label className="label" htmlFor="password">Password</label>
            <div style={{ position: "relative" }}>
              <input
                id="password"
                className="input"
                type={showPw ? "text" : "password"}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                style={{
                  position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                  background: "none", border: "none", cursor: "pointer",
                  color: "var(--text-tertiary)",
                }}
              >
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {error && (
            <div style={{
              padding: "10px 14px", marginBottom: 16,
              background: "#FEF2F2", border: "1px solid #FCA5A5",
              borderRadius: 8, color: "#DC2626", fontSize: 13,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            style={{ width: "100%" }}
            disabled={loading}
          >
            {loading ? <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} /> : "Sign In"}
          </button>
        </form>

        <div style={{
          marginTop: 28, padding: "16px", background: "var(--bg-secondary)",
          borderRadius: 8, fontSize: 12, color: "var(--text-tertiary)",
        }}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: "var(--text-secondary)" }}>
            Demo Credentials
          </div>
          <div style={{ display: "grid", gap: 4, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
            <div>admin@neurogut.demo / admin123</div>
            <div>clinician@neurogut.demo / clinician123</div>
            <div>researcher@neurogut.demo / researcher123</div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes float0 { 0%, 100% { transform: translate(0, 0) rotate(0deg); } 50% { transform: translate(30px, -30px) rotate(10deg); } }
        @keyframes float1 { 0%, 100% { transform: translate(0, 0); } 50% { transform: translate(-20px, 20px); } }
        @keyframes float2 { 0%, 100% { transform: translate(0, 0); } 50% { transform: translate(25px, 15px); } }
        @keyframes float3 { 0%, 100% { transform: translate(0, 0); } 50% { transform: translate(-15px, -25px); } }
        @keyframes float4 { 0%, 100% { transform: translate(0, 0); } 50% { transform: translate(20px, -10px); } }
        @keyframes float5 { 0%, 100% { transform: translate(0, 0); } 50% { transform: translate(-10px, 30px); } }
      `}</style>
    </div>
  );
}
