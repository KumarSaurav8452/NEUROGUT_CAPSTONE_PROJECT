"""SVM baseline and SHAP explanations for the deploy models.

Covers two project objectives the main pipeline did not: an SVM among the compared classifiers, and SHAP values
to explain the model. Both run on exactly the deploy setup (sczml.deploy): same features, same fold-local taxon
selection, same 5-fold split (seed 42) and, for SCZ, the same leave-one-study-out folds, so the SVM row is
directly comparable with the deployed ensemble.

  SVM   = StandardScaler + RBF SVC, C tuned by inner 3-fold CV, study x group balanced sample weights
  CI    = 95% bootstrap interval of the mean fold ROC-AUC (1000 resamples within fold x class)
  SHAP  = exact TreeSHAP of the deployed XGBoost model (xgboost pred_contribs), mean |SHAP| per taxon

python -m sczml.extras            -> results/extras/{scz,pd}.json + results/extras/EXTRAS.md
"""

from __future__ import annotations

import json
import sys
import warnings

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from sczml import data, deploy, models

OUT = deploy.ROOT / "results" / "extras"
SEED = deploy.SEED
ENSEMBLE, SVM = "Deployed ensemble (RF + XGB + EN)", "SVM (RBF kernel)"


def fit_svm(x: pd.DataFrame, y: pd.Series, w: np.ndarray):
    grid = GridSearchCV(make_pipeline(StandardScaler(), SVC(kernel="rbf", gamma="scale")),
                        {"svc__C": [0.3, 1.0, 3.0]}, cv=StratifiedKFold(3, shuffle=True, random_state=SEED),
                        scoring="roc_auc")
    return grid.fit(x, y, svc__sample_weight=w).best_estimator_


def run_folds(x, y, study, splits) -> tuple[dict, dict, np.ndarray]:
    """Per-fold AUC, out-of-fold scores and each sample's fold, for the deployed ensemble and the SVM."""
    folds = {ENSEMBLE: [], SVM: []}
    oof = {ENSEMBLE: np.full(len(y), np.nan), SVM: np.full(len(y), np.nan)}
    fold_of = np.empty(len(y), dtype=object)
    for name, tr, te in splits:
        fold_of[te] = name
        feats = deploy.choose(x.iloc[tr], y.iloc[tr], study.iloc[tr])
        w = models.balanced_weights(y.iloc[tr], study.iloc[tr])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scores = {ENSEMBLE: deploy.predict(deploy.fit(x.iloc[tr][feats], y.iloc[tr], w), x.iloc[te][feats]),
                      SVM: fit_svm(x.iloc[tr][feats], y.iloc[tr], w).decision_function(x.iloc[te][feats])}
        for m, s in scores.items():
            oof[m][te] = s
            folds[m].append(roc_auc_score(y.iloc[te], s))
        print(f"  {name}: ensemble {folds[ENSEMBLE][-1]:.3f}  svm {folds[SVM][-1]:.3f}", flush=True)
    return folds, oof, fold_of


def auc_ci(y, score, fold, n_boot: int = 1000, seed: int = SEED) -> tuple[float, float]:
    """95% bootstrap CI of the mean fold ROC-AUC, the number reported. Each replicate resamples cases and
    controls within every fold, recomputes each fold's AUC and averages them (scores are never pooled across
    folds, whose models and score scales differ)."""
    y, score, fold = np.asarray(y), np.asarray(score), np.asarray(fold)
    groups = [(np.flatnonzero((fold == f) & (y == 1)), np.flatnonzero((fold == f) & (y == 0))) for f in pd.unique(fold)]
    rng = np.random.default_rng(seed)
    aucs = []
    for _ in range(n_boot):
        per = []
        for pos, neg in groups:
            i = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
            per.append(roc_auc_score(y[i], score[i]))
        aucs.append(np.mean(per))
    lo, hi = np.percentile(aucs, [2.5, 97.5])
    return round(float(lo), 3), round(float(hi), 3)


def summarise(y: pd.Series, folds: list[float], score: np.ndarray, fold: np.ndarray) -> dict:
    """Mean fold AUC with a bootstrap CI, then accuracy / precision / recall / F1 at the Youden threshold."""
    fpr, tpr, thr = roc_curve(y, score)
    tn, fp, fn, tp = confusion_matrix(y, score >= thr[np.argmax(tpr - fpr)]).ravel()
    prec, rec = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return {"roc_auc": round(float(np.mean(folds)), 3), "roc_auc_sd": round(float(np.std(folds)), 3),
            "roc_auc_ci95": auc_ci(y, score, fold),
            "accuracy": round((tp + tn) / len(y), 3), "precision": round(prec, 3), "recall": round(rec, 3),
            "specificity": round(tn / max(tn + fp, 1), 3), "f1": round(2 * prec * rec / max(prec + rec, 1e-9), 3),
            "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}}


def shap_values(disease: str, x: pd.DataFrame, top: int = 15) -> list[dict]:
    """Exact TreeSHAP of the deployed XGBoost model on the training samples."""
    bundle = joblib.load(deploy.OUT / f"{disease}.joblib")
    feats = bundle["features"]
    contrib = bundle["models"]["XGBoost"].get_booster().predict(xgb.DMatrix(x[feats]), pred_contribs=True)[:, :-1]
    rows = []
    for j, f in enumerate(feats):
        r = np.corrcoef(x[f], contrib[:, j])[0, 1] if x[f].std() > 0 else 0.0
        rows.append({"taxon": data.short_name(f), "mean_abs_shap": round(float(np.abs(contrib[:, j]).mean()), 4),
                     "raises_score_when": "higher" if r >= 0 else "lower"})
    return sorted(rows, key=lambda d: -d["mean_abs_shap"])[:top]


def analyse(disease: str, frac: pd.DataFrame, y: pd.Series, study: pd.Series) -> dict:
    print(f"{disease}: {len(y)} samples", flush=True)
    x = deploy.log_features(frac)
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    strata = study.astype(str) + "/" + y.astype(str)
    designs = {"internal": [(str(k), tr, te) for k, (tr, te) in enumerate(cv.split(x, strata), 1)]}
    if study.nunique() > 1:
        designs["external"] = [(s, np.flatnonzero(study.values != s), np.flatnonzero(study.values == s))
                               for s in sorted(study.unique())]
    out = {"disease": disease, "n": int(len(y)), "n_cases": int(y.sum()), "external": None, "shap": shap_values(disease, x)}
    saved = []
    for design, splits in designs.items():
        folds, oof, fold_of = run_folds(x, y, study, splits)
        out[design] = {m: summarise(y, folds[m], oof[m], fold_of) for m in folds}
        saved.append(pd.DataFrame({"sample_id": y.index, "design": design, "fold": fold_of, "y": y.values, **oof}))
    pd.concat(saved).to_csv(OUT / f"{disease}_oof.csv", index=False)  # lets the CIs be recomputed without refitting
    return out


def report(results: list[dict]) -> str:
    lines = ["# SVM baseline and SHAP explanations", "", "Generated by `python -m sczml.extras` on the deploy setup "
             "(30 taxa, fold-local selection, seed 42). Thresholded metrics use the Youden threshold of pooled "
             "out-of-fold scores; the 95% CI is a 1000-sample bootstrap of the mean fold AUC (resampling within each fold).", ""]
    for r in results:
        lines += [f"## {deploy.DISEASE_LABEL[r['disease']]} ({r['n']} samples, {r['n_cases']} cases)", "",
                  "| validation | model | ROC-AUC | accuracy | precision | recall | F1 |", "|---|---|---|---|---|---|---|"]
        for split in ("internal", "external"):
            for m, s in (r[split] or {}).items():
                lines.append(f"| {split} | {m} | {s['roc_auc']} (95% CI {s['roc_auc_ci95'][0]}–{s['roc_auc_ci95'][1]}) | {s['accuracy']} | {s['precision']} "
                             f"| {s['recall']} | {s['f1']} |")
        lines += ["", "Top taxa by mean |SHAP| (deployed XGBoost):", "", "| taxon | mean abs SHAP | raises score when |",
                  "|---|---|---|"] + [f"| {t['taxon']} | {t['mean_abs_shap']} | {t['raises_score_when']} |" for t in r["shap"]] + [""]
    return "\n".join(lines)


def main(argv=None):
    which = (argv or sys.argv[1:]) or ["scz", "pd"]
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for d in which:
        if d == "scz":
            meta, frac, _, _ = data.load()
            res = analyse("scz", frac, meta["y"], meta["study_id"])
        else:
            frac, y, study = deploy.load_pd()
            res = analyse("pd", frac, y, study)
        (OUT / f"{d}.json").write_text(json.dumps(res, indent=1))
        results.append(res)
    if len(results) == 2:
        (OUT / "EXTRAS.md").write_text(report(results), encoding="utf-8")
    print("done ->", OUT, flush=True)


if __name__ == "__main__":
    main()
