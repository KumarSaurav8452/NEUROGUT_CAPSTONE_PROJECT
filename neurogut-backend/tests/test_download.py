"""Test report download with token query param."""
import requests

BASE = "http://127.0.0.1:8000"

# Login
r = requests.post(f"{BASE}/api/auth/login", json={"email": "clinician@neurogut.demo", "password": "clinician123"})
assert r.status_code == 200
TOKEN = r.json()["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
print(f"[OK] Logged in")

# Predict
r = requests.post(f"{BASE}/api/predict", json={
    "lachnospira": 9.0, "ruthenibacterium": 7.0, "veillonella": 4.0,
    "gardnerella": -4.5, "pseudobutyrivibrio": 2.0, "kocuria": -4.5,
    "trueperella": 0.1, "lancefieldella": -4.5, "fructilactobacillus": -4.5,
    "lachnoanaerobaculum": 2.0, "corynebacterium": 0.5, "raoultella": -4.5,
    "lawsonella": -2.0,
}, headers=HEADERS)
assert r.status_code == 200
pred_id = r.json()["prediction_id"]
print(f"[OK] Prediction: {pred_id[:12]}...")

# Generate report
r = requests.post(f"{BASE}/api/reports/generate", json={"prediction_id": pred_id}, headers=HEADERS)
assert r.status_code == 200
report_id = r.json()["id"]
print(f"[OK] Report generated: {report_id[:12]}...")

# Download WITHOUT token (should fail)
r = requests.get(f"{BASE}/api/reports/{report_id}/download")
print(f"[TEST] Download without token: {r.status_code} (expected 401)")
assert r.status_code == 401

# Download WITH token query param (should work)
r = requests.get(f"{BASE}/api/reports/{report_id}/download?token={TOKEN}")
print(f"[TEST] Download with ?token=: {r.status_code} (expected 200)")
assert r.status_code == 200
assert r.headers.get("content-type") == "application/pdf"
assert len(r.content) > 100
print(f"[OK] PDF size: {len(r.content)} bytes")
print(f"[OK] Content-Type: {r.headers.get('content-type')}")

print("\n=== REPORT DOWNLOAD FIX VERIFIED ===")
