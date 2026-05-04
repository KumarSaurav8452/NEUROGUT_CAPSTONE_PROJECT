import requests

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "clinician@neurogut.demo", "password": "clinician123"})
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}

# Test CSV upload
with open(r"c:\Major_project_Neuro_Gut\data\processed\frontend_validation_input.csv", "rb") as f:
    resp = requests.post(f"{BASE}/api/predict/csv", files={"file": ("test.csv", f, "text/csv")}, headers=H)

print(f"Status: {resp.status_code}")
data = resp.json()
print(f"Total: {data['total_rows']}, OK: {data['successful']}, Fail: {data['failed']}")
for p in data["predictions"][:3]:
    print(f"  Row {p['row']}: {p['risk_tier']} (Dep={p['depression_prob']:.2f}, Anx={p['anxiety_prob']:.2f})")
if data["errors"]:
    print(f"Errors: {data['errors']}")

# Test template download
r2 = requests.get(f"{BASE}/api/templates/csv")
print(f"\nTemplate: {r2.status_code}, lines={len(r2.text.strip().split(chr(10)))}")
print(r2.text[:200])
