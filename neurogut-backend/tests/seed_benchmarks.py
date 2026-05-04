"""Seed demo predictions to populate cohort benchmarks."""
import requests, random, time

BASE = "http://127.0.0.1:8000"

# Login
r = requests.post(f"{BASE}/api/auth/login", json={"email": "clinician@neurogut.demo", "password": "clinician123"})
TOKEN = r.json()["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}

# Get patients list, create some if needed
r = requests.get(f"{BASE}/api/patients?page=1&page_size=100", headers=H)
patients = r.json()["patients"]

# Create 8 demo patients if fewer than 8 exist
NEEDED = 8
for i in range(len(patients), NEEDED):
    age = random.randint(22, 65)
    sex = random.choice(["male", "female"])
    r = requests.post(f"{BASE}/api/patients", json={
        "patient_code": f"DEMO-{i+1:03d}", "age": age, "sex": sex,
        "notes": f"Demo patient for cohort benchmarking"
    }, headers=H)
    print(f"Created patient: {r.json()['patient_code']}")

# Refresh
r = requests.get(f"{BASE}/api/patients?page=1&page_size=100", headers=H)
patients = r.json()["patients"]

# Define sample profiles for each risk tier
PROFILES = {
    "healthy": [
        {"lachnospira": 9.0, "ruthenibacterium": 7.0, "veillonella": 1.5, "gardnerella": -5.0,
         "pseudobutyrivibrio": 3.0, "kocuria": -4.5, "trueperella": 0.1, "lancefieldella": -4.5,
         "fructilactobacillus": -4.5, "lachnoanaerobaculum": 2.0, "corynebacterium": 0.5,
         "raoultella": -4.5, "lawsonella": -3.0},
        {"lachnospira": 8.5, "ruthenibacterium": 6.5, "veillonella": 2.0, "gardnerella": -4.8,
         "pseudobutyrivibrio": 2.5, "kocuria": -4.0, "trueperella": 0.3, "lancefieldella": -4.0,
         "fructilactobacillus": -4.0, "lachnoanaerobaculum": 2.5, "corynebacterium": 0.8,
         "raoultella": -4.0, "lawsonella": -2.5},
    ],
    "depression": [
        {"lachnospira": 5.0, "ruthenibacterium": 4.0, "veillonella": 3.5, "gardnerella": -1.0,
         "pseudobutyrivibrio": 1.0, "kocuria": -2.0, "trueperella": 1.5, "lancefieldella": -2.0,
         "fructilactobacillus": -2.5, "lachnoanaerobaculum": 3.5, "corynebacterium": 3.0,
         "raoultella": -2.0, "lawsonella": 0.5},
        {"lachnospira": 4.5, "ruthenibacterium": 3.5, "veillonella": 4.0, "gardnerella": -0.5,
         "pseudobutyrivibrio": 0.5, "kocuria": -1.5, "trueperella": 2.0, "lancefieldella": -1.5,
         "fructilactobacillus": -2.0, "lachnoanaerobaculum": 4.0, "corynebacterium": 3.5,
         "raoultella": -1.5, "lawsonella": 1.0},
    ],
    "anxiety": [
        {"lachnospira": 6.0, "ruthenibacterium": 5.0, "veillonella": 5.0, "gardnerella": -2.5,
         "pseudobutyrivibrio": 1.5, "kocuria": -3.0, "trueperella": 0.5, "lancefieldella": -3.0,
         "fructilactobacillus": -3.0, "lachnoanaerobaculum": 3.0, "corynebacterium": 2.0,
         "raoultella": -3.0, "lawsonella": -1.0},
    ],
    "comorbid": [
        {"lachnospira": 3.0, "ruthenibacterium": 2.0, "veillonella": 6.0, "gardnerella": 2.0,
         "pseudobutyrivibrio": -0.5, "kocuria": 0.5, "trueperella": 3.0, "lancefieldella": 1.0,
         "fructilactobacillus": 2.0, "lachnoanaerobaculum": 5.0, "corynebacterium": 5.0,
         "raoultella": 1.0, "lawsonella": 3.0},
        {"lachnospira": 2.5, "ruthenibacterium": 1.5, "veillonella": 6.5, "gardnerella": 2.5,
         "pseudobutyrivibrio": -1.0, "kocuria": 1.0, "trueperella": 3.5, "lancefieldella": 1.5,
         "fructilactobacillus": 2.5, "lachnoanaerobaculum": 5.5, "corynebacterium": 5.5,
         "raoultella": 1.5, "lawsonella": 3.5},
    ],
}

# Run predictions linked to patients to populate DB
count = 0
pi = 0
for tier_name, profiles in PROFILES.items():
    for profile in profiles:
        if pi >= len(patients):
            break
        patient = patients[pi]
        pi += 1

        # Add small random noise to create variety
        noisy = {k: v + random.uniform(-0.3, 0.3) for k, v in profile.items()}

        # Create sample first
        sample_data = {
            "patient_id": patient["id"],
            "collection_date": f"2026-0{random.randint(1,4)}-{random.randint(10,28)}",
            **noisy,
        }
        sr = requests.post(f"{BASE}/api/samples", json=sample_data, headers=H)
        if sr.status_code != 200:
            print(f"  Sample create failed: {sr.text}")
            continue
        sample_id = sr.json()["id"]

        # Run prediction linked to sample
        pr = requests.post(f"{BASE}/api/predict?sample_id={sample_id}", json=noisy, headers=H)
        if pr.status_code == 200:
            result = pr.json()
            count += 1
            print(f"[{count}] Patient {patient['patient_code']}: {result['risk_tier']} (Dep={result['depression_prob']:.2f}, Anx={result['anxiety_prob']:.2f})")

print(f"\n=== Seeded {count} predictions ===")

# Now trigger benchmark recomputation
print("\nTriggering benchmark recomputation...")
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
