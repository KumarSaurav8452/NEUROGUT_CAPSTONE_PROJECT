"""Deployable single-sample models for the website (PRD_Website_v2.md, v2 predictions).

The research models (E1-E8) need a whole cohort (per-study scaling) or a full profile (CLR). A clinic scores
one patient at a time, possibly typing values by hand, so the deploy models use:
  features  = log10(relative abundance % + 0.01) of ~30 taxa (species/genus/family), each taxon on its own:
              no CLR and no per-cohort statistics, so a sample can be scored alone
  selection = taxa shared across cohorts, then cross-cohort consistent effects (models.select_consistent)
  models    = Random Forest + XGBoost + Elastic Net (sklearn/xgboost only: loads in the website backend)
The whole procedure is evaluated by CV (and leave-one-study-out for SCZ) before the final refit.

python -m sczml.deploy            -> results/deploy/{scz,pd}.joblib + {scz,pd}_metrics.json
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from sczml import data, models

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "deploy"
PD_XLSX = ROOT.parent / "external_repos" / "pd_repo" / "data" / "raw" / "Source_Data_24Oct2022.xlsx"
FLOOR_PCT = 0.01
N_FEATURES = 30
SEED = 42
DISEASE_LABEL = {"scz": "Schizophrenia", "pd": "Parkinson's disease"}


def log_features(frac: pd.DataFrame) -> pd.DataFrame:
    """Species fractions -> log10(% + floor) for species, genus and family."""
    multi = data.multi_level(frac) * 100.0
    return np.log10(multi.where(multi >= FLOOR_PCT, 0.0) + FLOOR_PCT)


def candidates(x: pd.DataFrame, study: pd.Series) -> list[str]:
    present = (x > np.log10(2 * FLOOR_PCT)).groupby(study.values).mean() > 0.10
    return list(x.columns[present.sum() >= np.ceil(present.shape[0] / 2)])


def choose(x: pd.DataFrame, y: pd.Series, study: pd.Series) -> list[str]:
    cand = candidates(x, study)
    z = x[cand].groupby(study.values).transform(lambda c: (c - c.mean()) / (c.std() or 1))
    return models.select_consistent(z, y, study, n_max=N_FEATURES)


def fit(x: pd.DataFrame, y: pd.Series, w: np.ndarray) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rf = RandomForestClassifier(n_estimators=500, max_depth=8, min_samples_leaf=3, random_state=SEED,
                                    n_jobs=-1).fit(x, y, sample_weight=w)
        xgb = XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                            eval_metric="logloss", random_state=SEED, n_jobs=4).fit(x, y, sample_weight=w)
        en = make_pipeline(StandardScaler(), LogisticRegressionCV(
            Cs=10, cv=5, solver="saga", l1_ratios=[0.1, 0.5, 0.9], max_iter=5000, scoring="roc_auc",
            random_state=SEED)).fit(x, y, logisticregressioncv__sample_weight=w)
    return {"Random Forest": rf, "XGBoost": xgb, "Elastic Net": en}


def predict(fitted: dict, x: pd.DataFrame) -> np.ndarray:
    return np.mean([m.predict_proba(x)[:, 1] for m in fitted.values()], axis=0)


def evaluate(x, y, study, splits) -> tuple[list[dict], np.ndarray]:
    rows, oof = [], np.full(len(y), np.nan)
    for name, tr, te in splits:
        feats = choose(x.iloc[tr], y.iloc[tr], study.iloc[tr])
        fitted = fit(x.iloc[tr][feats], y.iloc[tr], models.balanced_weights(y.iloc[tr], study.iloc[tr]))
        p = predict(fitted, x.iloc[te][feats])
        oof[te] = p
        rows.append({"fold": name, "n": len(te), "roc_auc": round(roc_auc_score(y.iloc[te], p), 3)})
        print(f"  {name}: AUC {rows[-1]['roc_auc']}", flush=True)
    return rows, oof


def build(disease: str, frac: pd.DataFrame, y: pd.Series, study: pd.Series, source: str):
    print(f"{disease}: {len(y)} samples ({int(y.sum())} cases), {study.nunique()} studies", flush=True)
    x = log_features(frac)
    strata = study.astype(str) + "/" + y.astype(str)
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    internal, oof = evaluate(x, y, study, [(str(k), tr, te) for k, (tr, te) in enumerate(cv.split(x, strata), 1)])
    loso = []
    if study.nunique() > 1:
        loso, _ = evaluate(x, y, study, [(s, np.flatnonzero(study.values != s), np.flatnonzero(study.values == s))
                                         for s in sorted(study.unique())])
    fpr, tpr, thr = roc_curve(y, oof)
    threshold = float(np.clip(thr[np.argmax(tpr - fpr)], 0.2, 0.8))
    pred = (oof >= threshold).astype(int)
    metrics = {
        "internal_auc": round(float(np.mean([r["roc_auc"] for r in internal])), 3),
        "internal_folds": internal,
        "external_auc": round(float(np.mean([r["roc_auc"] for r in loso])), 3) if loso else None,
        "external_folds": loso,
        "threshold": round(threshold, 3),
        "balanced_accuracy_at_threshold": round(balanced_accuracy_score(y, pred), 3),
        "f1_at_threshold": round(f1_score(y, pred), 3),
    }
    feats = choose(x, y, study)
    fitted = fit(x[feats], y, models.balanced_weights(y, study))
    hc, cases = x.loc[y.values == 0, feats], x.loc[y.values == 1, feats]
    reference = {f: {"healthy_mean": float(hc[f].mean()), "healthy_sd": float(hc[f].std() or 1.0),
                     "case_mean": float(cases[f].mean()),
                     "healthy_median_pct": float(np.median(10 ** hc[f] - FLOOR_PCT).clip(0))} for f in feats}
    bundle = {
        "disease": disease, "label": DISEASE_LABEL[disease], "version": "v2.0-deploy",
        "features": feats, "display": {f: data.short_name(f) for f in feats}, "floor_pct": FLOOR_PCT,
        "models": fitted, "threshold": threshold, "tiers": {"low": 0.35, "high": 0.65},
        "reference": reference, "metrics": metrics, "n_train": int(len(y)), "n_cases": int(y.sum()),
        "source": source,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, OUT / f"{disease}.joblib")
    (OUT / f"{disease}_metrics.json").write_text(json.dumps({k: v for k, v in bundle.items() if k != "models"}, indent=1))
    # Example upload: 6 training samples (3 per group), values in %, for demos only
    ex = (10 ** x.loc[:, feats] - FLOOR_PCT).clip(lower=0).round(4)
    pick = list(y[y == 1].index[:3]) + list(y[y == 0].index[:3])
    ex = ex.loc[pick].rename(columns=bundle["display"])
    ex.insert(0, "patient_code", [f"DEMO-{disease.upper()}-{i + 1}" for i in range(len(pick))])
    ex.to_csv(OUT / f"{disease}_example.csv", index=False)
    print(f"{disease}: internal {metrics['internal_auc']}, external {metrics['external_auc']}, "
          f"{len(feats)} features -> {OUT / (disease + '.joblib')}", flush=True)


def load_pd():
    meta = pd.read_excel(PD_XLSX, sheet_name="subject_metadata")
    rel = pd.read_excel(PD_XLSX, sheet_name="metaphlan_rel_ab", index_col=0)
    rel = rel[rel.index.str.contains(r"\|s__")]
    frac = (rel.T / 100.0)
    meta = meta[meta["Case_status"].isin(["PD", "Control"])].set_index("sample_name")
    frac = frac.reindex(meta.index).fillna(0.0)
    frac = frac.loc[:, frac.sum() > 0]
    frac = frac.div(frac.sum(axis=1).replace(0, 1), axis=0)
    y = (meta["Case_status"] == "PD").astype(int)
    return frac, y, pd.Series("Wallen_2022_PD", index=y.index)


def main(argv=None):
    which = (argv or sys.argv[1:]) or ["scz", "pd"]
    if "scz" in which:
        meta, frac, _, _ = data.load()
        build("scz", frac, meta["y"], meta["study_id"], "4 public SCZ cohorts (scz-microbiome-data)")
    if "pd" in which:
        frac, y, study = load_pd()
        build("pd", frac, y, study, "Wallen et al. 2022 Source Data (pd_repo/data/raw)")


if __name__ == "__main__":
    main()
