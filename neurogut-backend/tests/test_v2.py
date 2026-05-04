"""Test NEUROGUT v2.0 backend features."""
import requests

BASE = "http://127.0.0.1:8000"

# Login as clinician
r = requests.post(f"{BASE}/api/auth/login", json={"email": "clinician@neurogut.demo", "password": "clinician123"})
assert r.status_code == 200, f"Login failed: {r.text}"
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}
print(f"[OK] Login successful")

# Predict with CI
r = requests.post(f"{BASE}/api/predict", json={
    "lachnospira": 9, "ruthenibacterium": 7, "veillonella": 4,
    "gardnerella": -4.5, "pseudobutyrivibrio": 2, "kocuria": -4.5,
    "trueperella": 0.1, "lancefieldella": -4.5, "fructilactobacillus": -4.5,
    "lachnoanaerobaculum": 2, "corynebacterium": 0.5, "raoultella": -4.5,
    "lawsonella": -2,
}, headers=H)
assert r.status_code == 200, f"Predict failed: {r.text}"
d = r.json()
dep_ci_lo = d.get("depression_ci_low", -1)
dep_ci_hi = d.get("depression_ci_high", -1)
anx_ci_lo = d.get("anxiety_ci_low", -1)
anx_ci_hi = d.get("anxiety_ci_high", -1)
print(f"[OK] Prediction: Dep={d['depression_prob']:.3f} CI[{dep_ci_lo:.3f}-{dep_ci_hi:.3f}]")
print(f"                 Anx={d['anxiety_prob']:.3f} CI[{anx_ci_lo:.3f}-{anx_ci_hi:.3f}]")
print(f"                 Tier={d['risk_tier']}  Bootstrap={d.get('bootstrap_iterations')}")

# Alerts count
r = requests.get(f"{BASE}/api/alerts/count", headers=H)
assert r.status_code == 200, f"Alert count failed: {r.text}"
print(f"[OK] Alerts: {r.json()}")

# Alerts list
r = requests.get(f"{BASE}/api/alerts", headers=H)
assert r.status_code == 200, f"Alert list failed: {r.text}"
print(f"[OK] Alert list: {len(r.json())} alerts")

# Benchmarks
r = requests.get(f"{BASE}/api/benchmarks", headers=H)
assert r.status_code == 200, f"Benchmarks failed: {r.text}"
print(f"[OK] Benchmarks: {len(r.json())} entries")

# Login as admin
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@neurogut.demo", "password": "admin123"})
assert r.status_code == 200
ADMIN_H = {"Authorization": f"Bearer {r.json()['access_token']}"}

# Audit log
r = requests.get(f"{BASE}/api/audit", headers=ADMIN_H)
assert r.status_code == 200, f"Audit failed: {r.text}"
print(f"[OK] Audit log: {len(r.json())} entries")
for entry in r.json()[:3]:
    print(f"     {entry['action']} - {entry.get('resource_type', '-')} - {entry.get('created_at', '')[:19]}")

print("\n=== ALL v2.0 BACKEND TESTS PASSED ===")
