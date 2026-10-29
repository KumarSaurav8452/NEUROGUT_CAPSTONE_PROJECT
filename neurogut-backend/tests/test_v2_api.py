"""Automated tests for the v2 (schizophrenia / Parkinson's) prediction API.

Run from neurogut-backend:  .venv\\Scripts\\python -m pytest tests/test_v2_api.py -q
"""
import io

import pytest

from conftest import EXAMPLES

DISEASES = ("scz", "pd")


def medians(model: dict) -> dict:
    return {f["name"]: f["healthy_median_pct"] for f in model["features"]}


def check_result(r: dict, disease: str):
    assert r["disease"] == disease
    assert 0.0 <= r["probability"] <= 1.0
    assert r["risk_tier"] in ("low", "moderate", "high")
    assert set(r["model_probs"]) == {"Random Forest", "XGBoost", "Elastic Net"}
    assert 0 < len(r["drivers"]) <= 8
    assert r["id"] and r["created_at"]


# -- models and templates ---------------------------------------------------

def test_endpoints_require_login(client):
    assert client.get("/api/v2/models").status_code in (401, 403)
    assert client.post("/api/v2/predict", json={"disease": "scz", "abundances": {}}).status_code in (401, 403)


@pytest.mark.parametrize("disease", DISEASES)
def test_models_expose_features_and_metrics(models, disease):
    m = models[disease]
    assert len(m["features"]) == 30
    assert 0.0 < m["threshold"] < 1.0
    assert m["metrics"]["internal_auc"] > 0.5


def test_only_scz_has_external_validation(models):
    assert models["scz"]["metrics"]["external_auc"] is not None
    assert models["pd"]["metrics"]["external_auc"] is None


@pytest.mark.parametrize("disease", DISEASES)
def test_template_has_patient_code_and_all_taxa(client, auth, models, disease):
    r = client.get(f"/api/v2/templates/{disease}", headers=auth)
    assert r.status_code == 200
    header = r.text.splitlines()[0].split(",")
    assert header[:2] == ["patient_code", "collection_date"]
    assert set(header[2:]) == set(medians(models[disease]))


def test_unknown_disease_template(client, auth):
    assert client.get("/api/v2/templates/flu", headers=auth).status_code == 400


# -- single prediction ------------------------------------------------------

@pytest.mark.parametrize("disease", DISEASES)
def test_predict_typed_values(client, auth, models, disease):
    r = client.post("/api/v2/predict", headers=auth, json={"disease": disease, "abundances": medians(models[disease])})
    assert r.status_code == 200, r.text
    out = r.json()
    check_result(out, disease)
    assert out["missing_taxa"] == 0
    assert out["input_method"] == "manual"


def test_missing_taxa_are_counted(client, auth, models):
    one = dict(list(medians(models["scz"]).items())[:1])
    out = client.post("/api/v2/predict", headers=auth, json={"disease": "scz", "abundances": one}).json()
    assert out["missing_taxa"] == 29


def test_taxon_names_accept_any_spelling(client, auth, models):
    """'s__Collinsella_aerofaciens', 'Collinsella aerofaciens' and the full lineage score the same."""
    f = next(x for x in models["scz"]["features"] if x["name"].startswith("s__"))
    spellings = [f["name"], f["name"][3:].replace("_", " "), f["lineage"]]
    probs = {client.post("/api/v2/predict", headers=auth, json={"disease": "scz", "abundances": {s: 5.0}}).json()["probability"]
             for s in spellings}
    assert len(probs) == 1


def test_prediction_moves_with_input(client, auth, models):
    """Pushing every disease-higher taxon up must not lower the score."""
    feats = models["scz"]["features"]
    base = medians(models["scz"])
    shifted = {f["name"]: (base[f["name"]] + 5.0 if f["higher_in"] == "disease" else 0.0) for f in feats}
    p0 = client.post("/api/v2/predict", headers=auth, json={"disease": "scz", "abundances": base}).json()["probability"]
    p1 = client.post("/api/v2/predict", headers=auth, json={"disease": "scz", "abundances": shifted}).json()["probability"]
    assert p1 >= p0


def test_invalid_disease_rejected(client, auth):
    r = client.post("/api/v2/predict", headers=auth, json={"disease": "flu", "abundances": {"x": 1}})
    assert r.status_code == 422


def test_unknown_patient_rejected(client, auth, models):
    r = client.post("/api/v2/predict", headers=auth,
                    json={"disease": "scz", "patient_id": "no-such-patient", "abundances": medians(models["scz"])})
    assert r.status_code == 404


# -- file uploads -----------------------------------------------------------

def upload(client, auth, disease, name, content: bytes):
    return client.post("/api/v2/predict/csv", headers=auth, data={"disease": disease},
                       files={"file": (name, io.BytesIO(content), "text/csv")})


@pytest.mark.parametrize("disease", DISEASES)
def test_example_csv_upload(client, auth, disease):
    r = upload(client, auth, disease, "example.csv", (EXAMPLES / f"{disease}_example.csv").read_bytes())
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["format"] == "rows" and out["n_predicted"] == 6 and out["errors"] == []
    for res in out["results"]:
        check_result(res, disease)
        assert res["input_method"] == "csv_upload"


def test_metaphlan_profile_upload(client, auth):
    r = upload(client, auth, "scz", "xu.tsv", (EXAMPLES / "scz_metaphlan_profile_Xu_heldout.tsv").read_bytes())
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["format"] == "profile" and out["n_predicted"] == 5
    assert all(res["input_method"] == "profile_upload" for res in out["results"])


def test_bad_rows_are_reported_not_fatal(client, auth, models):
    names = list(medians(models["scz"]))[:2]
    csv = f"patient_code,{names[0]},{names[1]}\nOK-1,1.0,2.0\nBAD-1,abc,2.0\n".encode()
    out = upload(client, auth, "scz", "mixed.csv", csv).json()
    assert out["n_predicted"] == 1
    assert len(out["errors"]) == 1 and out["errors"][0]["row"] == 3


def test_csv_without_model_taxa(client, auth):
    out = upload(client, auth, "scz", "wrong.csv", b"patient_code,foo,bar\nP1,1,2\n").json()
    assert out["n_predicted"] == 0 and "template" in out["errors"][0]["error"]


def test_empty_file_rejected(client, auth):
    assert upload(client, auth, "scz", "empty.csv", b"   ").status_code == 400


# -- history ----------------------------------------------------------------

def test_history_filters_by_disease_and_fetches_one(client, auth, models):
    made = client.post("/api/v2/predict", headers=auth, json={"disease": "pd", "abundances": medians(models["pd"])}).json()
    rows = client.get("/api/v2/predictions", headers=auth, params={"disease": "pd"}).json()
    assert rows and all(r["disease"] == "pd" for r in rows)
    assert rows[0]["id"] == made["id"]  # newest first
    one = client.get(f"/api/v2/predictions/{made['id']}", headers=auth)
    assert one.status_code == 200 and one.json()["probability"] == made["probability"]


def test_missing_prediction_404(client, auth):
    assert client.get("/api/v2/predictions/does-not-exist", headers=auth).status_code == 404


# -- input validation -------------------------------------------------------

def species(model: dict) -> list[str]:
    return [f["name"] for f in model["features"] if f["name"].startswith("s__")]


@pytest.mark.parametrize("value", [-1.0, 150.0])
def test_out_of_range_value_rejected(client, auth, models, value):
    name = species(models["scz"])[0]
    r = client.post("/api/v2/predict", headers=auth, json={"disease": "scz", "abundances": {name: value}})
    assert r.status_code == 422
    assert name in r.json()["detail"] and "0-100" in r.json()["detail"]


def test_rank_total_above_100_rejected(client, auth, models):
    names = species(models["scz"])[:3]
    r = client.post("/api/v2/predict", headers=auth, json={"disease": "scz", "abundances": {n: 40.0 for n in names}})
    assert r.status_code == 422 and "species values add up to 120.0" in r.json()["detail"]


def test_genus_and_species_totals_checked_separately(client, auth, models):
    """A genus and its own species may both be large: each rank is its own composition."""
    feats = models["scz"]["features"]
    g = next(f["name"] for f in feats if f["name"].startswith("g__"))
    s = next(f["name"] for f in feats if f["name"].startswith("s__"))
    r = client.post("/api/v2/predict", headers=auth, json={"disease": "scz", "abundances": {g: 60.0, s: 60.0}})
    assert r.status_code == 200, r.text


def test_invalid_csv_row_reported_others_scored(client, auth, models):
    name = species(models["pd"])[0]
    csv = f"patient_code,{name}\nOK-1,2.0\nNEG-1,-5\nBIG-1,300\n".encode()
    out = upload(client, auth, "pd", "ranges.csv", csv).json()
    assert out["n_predicted"] == 1
    assert [e["row"] for e in out["errors"]] == [3, 4]
    assert all("outside 0-100" in e["error"] for e in out["errors"])
