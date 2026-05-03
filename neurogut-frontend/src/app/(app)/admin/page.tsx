"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { Shield, Plus, UserCheck, UserX } from "lucide-react";

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [showInvite, setShowInvite] = useState(false);
  const [form, setForm] = useState({ email: "", role: "clinician", full_name: "" });
  const [saving, setSaving] = useState(false);

  const load = () => api.listUsers().then(setUsers).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.inviteUser(form.email, form.role, form.full_name);
      setShowInvite(false);
      setForm({ email: "", role: "clinician", full_name: "" });
      load();
    } catch { /* ignore */ }
    finally { setSaving(false); }
  };

  const handleToggle = async (id: string) => {
    await api.toggleUser(id);
    load();
  };

  return (
    <>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>User Management</h1>
          <p>Manage hospital users and permissions</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowInvite(true)}>
          <Plus size={16} /> Invite User
        </button>
      </div>

      <div className="page-body">
        {showInvite && (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}
            onClick={() => setShowInvite(false)}>
            <div className="card animate-fade-in" style={{ padding: 28, width: 420 }} onClick={(e) => e.stopPropagation()}>
              <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Invite User</h2>
              <form onSubmit={handleInvite}>
                <div style={{ marginBottom: 16 }}>
                  <label className="label">Email *</label>
                  <input className="input" type="email" required value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })} />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label className="label">Full Name</label>
                  <input className="input" value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
                </div>
                <div style={{ marginBottom: 20 }}>
                  <label className="label">Role</label>
                  <select className="input" value={form.role}
                    onChange={(e) => setForm({ ...form, role: e.target.value })}>
                    <option value="clinician">Clinician</option>
                    <option value="researcher">Researcher</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                  <button className="btn btn-primary" type="submit" disabled={saving} style={{ flex: 1 }}>
                    {saving ? "Sending..." : "Send Invite"}
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={() => setShowInvite(false)}>Cancel</button>
                </div>
              </form>
            </div>
          </div>
        )}

        <div className="card" style={{ overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Login</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 600 }}>{u.full_name || "--"}</td>
                  <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>{u.email}</td>
                  <td><span className="badge badge-info" style={{ textTransform: "capitalize" }}>{u.role}</span></td>
                  <td>
                    <span className={`badge ${u.is_active ? "badge-healthy" : "badge-high"}`}>
                      {u.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                  </td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={() => handleToggle(u.id)}
                      title={u.is_active ? "Disable" : "Enable"}>
                      {u.is_active ? <UserX size={14} /> : <UserCheck size={14} />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
