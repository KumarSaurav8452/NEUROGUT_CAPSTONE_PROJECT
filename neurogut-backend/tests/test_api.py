"""Quick API integration test for NEUROGUT backend."""
import requests
import json
import sys

BASE = "http://127.0.0.1:8000"

def main():
    print("=" * 60)
    print("NEUROGUT API Integration Test")
    print("=" * 60)

    # 1. Root
    print("\n[1] Root endpoint...")
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200
    print(f"    OK: {r.json()['service']}")

    # 2. Model health
    print("\n[2] Model health...")
    r = requests.get(f"{BASE}/api/model/health")
    assert r.status_code == 200
    health = r.json()
    print(f"    Model loaded: {health['model_loaded']}")
    print(f"    Version: {health['model_version']}")
    print(f"    Features: {health['feature_count']}")

    # 3. Login as clinician
    print("\n[3] Login (clinician)...")
    r = requests.post(f"{BASE}/api/auth/login", json={
        "email": "clinician@neurogut.demo",
        "password": "clinician123",
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    tok = r.json()
    TOKEN = tok["access_token"]
    HEADERS = {"Authorization": f"Bearer {TOKEN}"}
    print(f"    Logged in as: {tok['full_name']} ({tok['role']})")

    # 4. Auth /me
    print("\n[4] Auth /me...")
    r = requests.get(f"{BASE}/api/auth/me", headers=HEADERS)
    assert r.status_code == 200
    print(f"    Email: {r.json()['email']}")

    # 5. Create patient
    print("\n[5] Create patient...")
    r = requests.post(f"{BASE}/api/patients", json={
        "patient_code": "PAT-001",
        "age": 45,
        "sex": "female",
        "notes": "Test patient for integration testing",
    }, headers=HEADERS)
    assert r.status_code == 200, f"Create patient failed: {r.text}"
    patient = r.json()
    print(f"    Patient ID: {patient['id'][:12]}...")

    # 6. Submit sample
    print("\n[6] Submit sample...")
    r = requests.post(f"{BASE}/api/samples", json={
        "patient_id": patient["id"],
        "collection_date": "2025-05-01",
        "input_method": "manual",
        "lachnospira": 9.0,
        "ruthenibacterium": 7.0,
        "veillonella": 4.0,
        "gardnerella": -4.5,
        "pseudobutyrivibrio": 2.0,
        "kocuria": -4.5,
        "trueperella": 0.1,
        "lancefieldella": -4.5,
        "fructilactobacillus": -4.5,
        "lachnoanaerobaculum": 2.0,
        "corynebacterium": 0.5,
        "raoultella": -4.5,
        "lawsonella": -2.0,
    }, headers=HEADERS)
    assert r.status_code == 200, f"Submit sample failed: {r.text}"
    sample = r.json()
    print(f"    Sample ID: {sample['id'][:12]}...")

    # 7. Predict (healthy profile)
    print("\n[7] Predict (healthy profile)...")
    r = requests.post(f"{BASE}/api/predict", json={
        "lachnospira": 9.0,
        "ruthenibacterium": 7.0,
        "veillonella": 4.0,
        "gardnerella": -4.5,
        "pseudobutyrivibrio": 2.0,
        "kocuria": -4.5,
        "trueperella": 0.1,
        "lancefieldella": -4.5,
        "fructilactobacillus": -4.5,
        "lachnoanaerobaculum": 2.0,
        "corynebacterium": 0.5,
        "raoultella": -4.5,
        "lawsonella": -2.0,
    }, params={"sample_id": sample["id"]}, headers=HEADERS)
    assert r.status_code == 200, f"Predict failed: {r.text}"
    pred = r.json()
    print(f"    Depression: prob={pred['depression_prob']:.3f} label={pred['depression_label']}")
    print(f"    Anxiety:    prob={pred['anxiety_prob']:.3f} label={pred['anxiety_label']}")
    print(f"    Risk Tier:  {pred['risk_tier']}")
    print(f"    Consensus:  {pred['consensus_features']}")
    print(f"    Latency:    {pred['processing_time_ms']}ms")

    # 8. Predict (depression profile)
    print("\n[8] Predict (depression profile)...")
    r = requests.post(f"{BASE}/api/predict", json={
        "lachnospira": 5.0,
        "ruthenibacterium": 9.5,
        "veillonella": 4.0,
        "gardnerella": -1.5,
        "pseudobutyrivibrio": 0.5,
        "kocuria": 2.5,
        "trueperella": 3.5,
        "lancefieldella": 0.7,
        "fructilactobacillus": -4.5,
        "lachnoanaerobaculum": 0.1,
        "corynebacterium": 2.4,
        "raoultella": 0.3,
        "lawsonella": -0.3,
    }, headers=HEADERS)
    assert r.status_code == 200
    pred2 = r.json()
    print(f"    Depression: prob={pred2['depression_prob']:.3f} label={pred2['depression_label']}")
    print(f"    Anxiety:    prob={pred2['anxiety_prob']:.3f} label={pred2['anxiety_label']}")
    print(f"    Risk Tier:  {pred2['risk_tier']}")

    # 9. Generate PDF report
    print("\n[9] Generate PDF report...")
    r = requests.post(f"{BASE}/api/reports/generate", json={
        "prediction_id": pred["prediction_id"],
    }, headers=HEADERS)
    assert r.status_code == 200, f"Report gen failed: {r.text}"
    report = r.json()
    print(f"    Report ID: {report['id'][:12]}...")
    print(f"    File: {report['file_path']}")

    # 10. List patients
    print("\n[10] List patients...")
    r = requests.get(f"{BASE}/api/patients", headers=HEADERS)
    assert r.status_code == 200
    pl = r.json()
    print(f"    Total patients: {pl['total']}")

    # 11. Get patient profile
    print("\n[11] Get patient profile...")
    r = requests.get(f"{BASE}/api/patients/{patient['id']}", headers=HEADERS)
    assert r.status_code == 200
    pp = r.json()
    print(f"    Code: {pp['patient_code']}")
    print(f"    Samples: {len(pp['samples'])}")

    # 12. Login as admin + list users
    print("\n[12] Admin: list users...")
    r = requests.post(f"{BASE}/api/auth/login", json={
        "email": "admin@neurogut.demo",
        "password": "admin123",
    })
    admin_token = r.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE}/api/admin/users", headers=admin_headers)
    assert r.status_code == 200
    users = r.json()
    print(f"    Users in hospital: {len(users)}")
    for u in users:
        print(f"      - {u['email']} ({u['role']})")

    # 13. List reports
    print("\n[13] List reports...")
    r = requests.get(f"{BASE}/api/reports/", headers=HEADERS)
    assert r.status_code == 200
    print(f"    Reports: {len(r.json())}")

    print("\n" + "=" * 60)
    print("ALL 13 API TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
