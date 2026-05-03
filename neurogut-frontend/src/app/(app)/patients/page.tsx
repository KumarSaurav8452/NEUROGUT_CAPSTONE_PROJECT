"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Patient } from "@/lib/types";
import { Users, Plus, Search, ChevronRight } from "lucide-react";
import Link from "next/link";

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ patient_code: "", age: "", sex: "prefer_not_to_say", notes: "" });
  const [creating, setCreating] = useState(false);

  const load = (p = 1, s = search) => {
    api.listPatients(p, 20, s).then((r) => {
      setPatients(r.patients);
      setTotal(r.total);
      setPage(r.page);
    }).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createPatient({
        patient_code: form.patient_code,
        age: form.age ? parseInt(form.age) : undefined,
        sex: form.sex,
        notes: form.notes,
      });
      setShowCreate(false);
      setForm({ patient_code: "", age: "", sex: "prefer_not_to_say", notes: "" });
      load();
    } catch { /* ignore */ }
    finally { setCreating(false); }
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>Patients</h1>
          <p>{total} registered patients</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} /> Add Patient
        </button>
      </div>

      <div className="page-body">
        {/* Search */}
        <div style={{ marginBottom: 20, position: "relative", maxWidth: 400 }}>
          <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-tertiary)" }} />
          <input
            className="input"
            placeholder="Search by patient code..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); load(1, e.target.value); }}
            style={{ paddingLeft: 36 }}
          />
        </div>

        {/* Create Modal */}
        {showCreate && (
          <div style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50,
          }} onClick={() => setShowCreate(false)}>
            <div className="card animate-fade-in" style={{ padding: 28, width: 440 }} onClick={(e) => e.stopPropagation()}>
              <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Register New Patient</h2>
              <form onSubmit={handleCreate}>
                <div style={{ marginBottom: 16 }}>
                  <label className="label">Patient Code *</label>
                  <input className="input" required value={form.patient_code}
                    onChange={(e) => setForm({ ...form, patient_code: e.target.value })}
                    placeholder="e.g. PAT-001" />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                  <div>
                    <label className="label">Age</label>
                    <input className="input" type="number" min="1" max="119" value={form.age}
                      onChange={(e) => setForm({ ...form, age: e.target.value })} placeholder="e.g. 45" />
                  </div>
                  <div>
                    <label className="label">Sex</label>
                    <select className="input" value={form.sex}
                      onChange={(e) => setForm({ ...form, sex: e.target.value })}>
                      <option value="prefer_not_to_say">Prefer not to say</option>
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>
                <div style={{ marginBottom: 20 }}>
                  <label className="label">Notes</label>
                  <textarea className="input" rows={2} value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    placeholder="Optional clinical notes" />
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                  <button className="btn btn-primary" type="submit" disabled={creating} style={{ flex: 1 }}>
                    {creating ? "Creating..." : "Register Patient"}
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="card" style={{ overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Patient Code</th>
                <th>Age</th>
                <th>Sex</th>
                <th>Notes</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {patients.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: "center", padding: 40, color: "var(--text-tertiary)" }}>
                  No patients found. Click &quot;Add Patient&quot; to register one.
                </td></tr>
              )}
              {patients.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{p.patient_code}</td>
                  <td>{p.age ?? "--"}</td>
                  <td style={{ textTransform: "capitalize" }}>{p.sex.replace("_", " ")}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.notes || "--"}</td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                    {p.created_at ? new Date(p.created_at).toLocaleDateString() : "--"}
                  </td>
                  <td>
                    <Link href={`/patients/${p.id}`} className="btn btn-ghost btn-sm">
                      <ChevronRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 20 }}>
            {Array.from({ length: totalPages }, (_, i) => (
              <button key={i} className={`btn btn-sm ${page === i + 1 ? "btn-primary" : "btn-ghost"}`}
                onClick={() => load(i + 1)}>
                {i + 1}
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
