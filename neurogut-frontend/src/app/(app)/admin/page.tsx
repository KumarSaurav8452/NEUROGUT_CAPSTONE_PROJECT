"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import {
  Shield, Plus, UserCheck, UserX, Search, ChevronLeft,
  ChevronRight, RefreshCw, MoreHorizontal, Edit2, Mail,
} from "lucide-react";
import { RoleGuard } from "@/components/RoleGuard";

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------
const ROLE_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  admin:      { bg: "#1E3A5F", color: "#fff",    label: "Admin" },
  clinician:  { bg: "#1D4ED8", color: "#fff",    label: "Clinician" },
  researcher: { bg: "#0F766E", color: "#fff",    label: "Researcher" },
};

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  active:      { bg: "#DCFCE7", color: "#166534", label: "Active" },
  invited:     { bg: "#FEF9C3", color: "#854D0E", label: "Invited" },
  deactivated: { bg: "#FEE2E2", color: "#991B1B", label: "Deactivated" },
};

function RolePill({ role }: { role: string }) {
  const cfg = ROLE_BADGE[role] ?? { bg: "#E5E7EB", color: "#374151", label: role };
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: "2px 10px", borderRadius: 20,
      background: cfg.bg, color: cfg.color, textTransform: "capitalize", letterSpacing: 0.3,
    }}>
      {cfg.label}
    </span>
  );
}

function StatusPill({ status }: { status: string }) {
  const cfg = STATUS_BADGE[status] ?? { bg: "#E5E7EB", color: "#374151", label: status };
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: "2px 10px", borderRadius: 20,
      background: cfg.bg, color: cfg.color, textTransform: "capitalize", letterSpacing: 0.3,
    }}>
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Add User Modal
// ---------------------------------------------------------------------------
interface AddUserModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

function AddUserModal({ onClose, onSuccess }: AddUserModalProps) {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    role: "clinician",
    welcome_message: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createUser(form);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send invitation");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}
      onClick={onClose}
    >
      <div
        className="card animate-fade-in"
        style={{ padding: 32, width: 460, maxWidth: "calc(100vw - 32px)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10, background: "var(--primary-light)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Shield size={18} color="var(--primary)" />
          </div>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Add User</h2>
            <p style={{ fontSize: 12, color: "var(--text-tertiary)", margin: 0 }}>
              An invitation email will be sent with a magic link.
            </p>
          </div>
        </div>

        {error && (
          <div style={{
            background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8,
            padding: "10px 14px", marginBottom: 16, fontSize: 13, color: "#B91C1C",
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label className="label">Full Name</label>
            <input
              className="input"
              placeholder="Dr. Jane Smith"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="label">Email *</label>
            <input
              className="input"
              type="email"
              required
              placeholder="jane@hospital.org"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="label">Role *</label>
            <select
              className="input"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="clinician">Clinician</option>
              <option value="researcher">Researcher</option>
              <option value="admin">Admin</option>
            </select>
            <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4, marginBottom: 0 }}>
              {form.role === "clinician" && "Can view patients, run analyses, and generate reports."}
              {form.role === "researcher" && "Can batch upload, export data, and view cohort benchmarks. No patient PII access."}
              {form.role === "admin" && "Full access including user management."}
            </p>
          </div>

          <div style={{ marginBottom: 24 }}>
            <label className="label">Welcome Message <span style={{ color: "var(--text-tertiary)", fontWeight: 400 }}>(optional)</span></label>
            <textarea
              className="input"
              rows={2}
              placeholder="e.g. Looking forward to having you on the team!"
              value={form.welcome_message}
              onChange={(e) => setForm({ ...form, welcome_message: e.target.value })}
              style={{ resize: "vertical" }}
            />
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-primary" type="submit" disabled={saving} style={{ flex: 1 }}>
              <Mail size={15} />
              {saving ? "Sending..." : "Send Invitation"}
            </button>
            <button className="btn btn-secondary" type="button" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit Role Popover (inline dropdown)
// ---------------------------------------------------------------------------
interface EditRoleProps {
  user: User;
  onUpdated: (u: User) => void;
}

function EditRoleDropdown({ user, onUpdated }: EditRoleProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleChange = async (newRole: string) => {
    if (newRole === user.role) { setOpen(false); return; }
    setSaving(true);
    try {
      const updated = await api.updateUserRole(user.id, newRole);
      onUpdated(updated);
    } catch { /* ignore */ }
    finally { setSaving(false); setOpen(false); }
  };

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        className="btn btn-ghost btn-sm"
        onClick={() => setOpen((o) => !o)}
        title="Edit role"
        disabled={saving}
      >
        <Edit2 size={13} />
      </button>
      {open && (
        <div style={{
          position: "absolute", right: 0, top: "100%", zIndex: 20,
          background: "white", border: "1px solid var(--border-color)",
          borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
          minWidth: 140, overflow: "hidden",
        }}>
          {["clinician", "researcher", "admin"].map((r) => (
            <button
              key={r}
              onClick={() => handleChange(r)}
              style={{
                display: "block", width: "100%", padding: "9px 14px",
                textAlign: "left", background: r === user.role ? "var(--primary-light)" : "white",
                border: "none", cursor: "pointer", fontSize: 13,
                fontWeight: r === user.role ? 700 : 400,
                color: r === user.role ? "var(--primary)" : "var(--text-primary)",
              }}
            >
              {r.charAt(0).toUpperCase() + r.slice(1)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Admin Page
// ---------------------------------------------------------------------------
function AdminPageContent() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddUser, setShowAddUser] = useState(false);
  const [toast, setToast] = useState("");

  // Filters
  const [search, setSearch] = useState("");
  const [filterRole, setFilterRole] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [page, setPage] = useState(1);

  const PAGE_SIZE = 25;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listUsers({
        search: search || undefined,
        role: filterRole || undefined,
        status: filterStatus || undefined,
        page,
      });
      setUsers(result);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [search, filterRole, filterStatus, page]);

  useEffect(() => { load(); }, [load]);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); load(); }, 400);
    return () => clearTimeout(t);
  }, [search]); // eslint-disable-line

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const handleUserUpdated = (updated: User) => {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
  };

  const handleDeactivate = async (u: User) => {
    try {
      const updated = await api.deactivateUser(u.id);
      handleUserUpdated(updated);
      showToast(`${u.full_name || u.email} deactivated`);
    } catch { /* ignore */ }
  };

  const handleActivate = async (u: User) => {
    try {
      const updated = await api.activateUser(u.id);
      handleUserUpdated(updated);
      showToast(`${u.full_name || u.email} reactivated`);
    } catch { /* ignore */ }
  };

  const handleReinvite = async (u: User) => {
    try {
      await api.reinviteUser(u.id);
      showToast(`Invitation resent to ${u.email}`);
    } catch { /* ignore */ }
  };

  const totalShowing = users.length;
  const hasMore = users.length === PAGE_SIZE;

  return (
    <>
      {/* Toast */}
      {toast && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 100,
          background: "#1E293B", color: "white", padding: "12px 20px",
          borderRadius: 10, fontSize: 14, fontWeight: 500,
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
          animation: "slideIn 0.2s ease",
        }}>
          {toast}
        </div>
      )}

      {/* Add User Modal */}
      {showAddUser && (
        <AddUserModal
          onClose={() => setShowAddUser(false)}
          onSuccess={() => { load(); showToast("Invitation sent successfully!"); }}
        />
      )}

      {/* Page Header */}
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>User Management</h1>
          <p>Manage hospital users, roles, and access</p>
        </div>
        <button id="add-user-btn" className="btn btn-primary" onClick={() => setShowAddUser(true)}>
          <Plus size={16} /> Add User
        </button>
      </div>

      <div className="page-body">
        {/* Filters Row */}
        <div className="card" style={{ padding: "16px 20px", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            {/* Search */}
            <div style={{ flex: 1, minWidth: 200, position: "relative" }}>
              <Search size={15} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: "var(--text-tertiary)" }} />
              <input
                className="input"
                placeholder="Search by name or email…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 34, margin: 0 }}
              />
            </div>

            {/* Role filter */}
            <select
              className="input"
              value={filterRole}
              onChange={(e) => { setFilterRole(e.target.value); setPage(1); }}
              style={{ width: 150, margin: 0 }}
            >
              <option value="">All Roles</option>
              <option value="clinician">Clinician</option>
              <option value="researcher">Researcher</option>
              <option value="admin">Admin</option>
            </select>

            {/* Status filter */}
            <select
              className="input"
              value={filterStatus}
              onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
              style={{ width: 160, margin: 0 }}
            >
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="invited">Invited</option>
              <option value="deactivated">Deactivated</option>
            </select>

            <button className="btn btn-ghost btn-sm" onClick={load} title="Refresh">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* User Table */}
        <div className="card" style={{ overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 48, textAlign: "center" }}>
              <div className="spinner" style={{ margin: "0 auto" }} />
            </div>
          ) : users.length === 0 ? (
            <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--text-tertiary)" }}>
              <Shield size={40} style={{ marginBottom: 12, opacity: 0.3 }} />
              <p style={{ margin: 0 }}>No users found matching your filters.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Login</th>
                  <th>Date Added</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: "50%",
                          background: "var(--primary-light)",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 12, fontWeight: 700, color: "var(--primary)", flexShrink: 0,
                        }}>
                          {(u.full_name || u.email).slice(0, 2).toUpperCase()}
                        </div>
                        {u.full_name || <span style={{ color: "var(--text-tertiary)", fontStyle: "italic", fontWeight: 400 }}>No name</span>}
                      </div>
                    </td>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>{u.email}</td>
                    <td><RolePill role={u.role} /></td>
                    <td><StatusPill status={u.status ?? (u.is_active ? "active" : "deactivated")} /></td>
                    <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : "Never"}
                    </td>
                    <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                        {/* Edit role */}
                        <EditRoleDropdown user={u} onUpdated={handleUserUpdated} />

                        {/* Re-invite (for invited or deactivated users) */}
                        {(u.status === "invited" || u.status === "deactivated") && (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => handleReinvite(u)}
                            title="Resend invitation"
                          >
                            <Mail size={13} />
                          </button>
                        )}

                        {/* Activate / Deactivate */}
                        {u.status !== "deactivated" ? (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => handleDeactivate(u)}
                            title="Deactivate user"
                            style={{ color: "#EF4444" }}
                          >
                            <UserX size={13} />
                          </button>
                        ) : (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => handleActivate(u)}
                            title="Activate user"
                            style={{ color: "#22C55E" }}
                          >
                            <UserCheck size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Pagination */}
          {(page > 1 || hasMore) && (
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "12px 20px", borderTop: "1px solid var(--border-light)",
            }}>
              <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                Showing {(page - 1) * PAGE_SIZE + 1}–{(page - 1) * PAGE_SIZE + totalShowing}
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!hasMore}
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Export wrapped in RoleGuard (admin only)
// ---------------------------------------------------------------------------
export default function AdminPage() {
  return (
    <RoleGuard allowedRoles={["admin"]}>
      <AdminPageContent />
    </RoleGuard>
  );
}
