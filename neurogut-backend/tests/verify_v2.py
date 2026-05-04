import requests
r = requests.post("http://127.0.0.1:8000/api/auth/login", json={"email": "clinician@neurogut.demo", "password": "clinician123"})
H = {"Authorization": f"Bearer {r.json()['access_token']}"}
r2 = requests.get("http://127.0.0.1:8000/api/benchmarks", headers=H)
data = r2.json()
print(f"{len(data)} benchmarks")
tiers = set(b["risk_tier"] for b in data)
print(f"Tiers: {tiers}")
for b in data[:3]:
    print(f"  {b['taxon_name']:20s} | {b['risk_tier']:18s} | mean={b['mean_value']:.3f} | p50={b['p50_value']:.3f} | n={b['sample_count']}")

# Check alerts
r3 = requests.get("http://127.0.0.1:8000/api/alerts/count", headers=H)
print(f"\nAlerts: {r3.json()}")
