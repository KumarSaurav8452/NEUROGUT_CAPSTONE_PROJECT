"""Fold-local Boruta -> Elastic-Net selection and the four PD-arm models (+ mean ensemble)."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from boruta import BorutaPy
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegressionCV
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

SEED = 42
FULL = {
    "xgb": {"n_estimators": [50, 100], "max_depth": [3, 5, 7], "learning_rate": [0.01, 0.1]},
    "cat": {"iterations": [100, 200], "depth": [4, 6, 8], "learning_rate": [0.03, 0.1]},
    "boruta_iter": 100,
}
QUICK = {
    "xgb": {"n_estimators": [50], "max_depth": [3], "learning_rate": [0.1]},
    "cat": {"iterations": [100], "depth": [4], "learning_rate": [0.1]},
    "boruta_iter": 20,
}
BASE_MODELS = ["Random Forest", "XGBoost", "CatBoost"]


def _en(cv=5):
    # Scaled, unlike PD v12: the L1/L2 penalty is not scale-invariant and the extras are on other scales.
    return make_pipeline(StandardScaler(), LogisticRegressionCV(
        Cs=10, cv=cv, solver="saga", l1_ratios=[0.1, 0.5, 0.9, 1.0], max_iter=5000, scoring="roc_auc",
        class_weight="balanced", random_state=SEED))


def select_features(x: pd.DataFrame, y: pd.Series, grids=FULL) -> list[str]:
    """Boruta (all-relevant) then Elastic Net (non-zero coefficients), training rows only."""
    rf = RandomForestClassifier(n_jobs=-1, class_weight="balanced", max_depth=5, random_state=SEED)
    bor = BorutaPy(rf, n_estimators="auto", max_iter=grids["boruta_iter"], random_state=SEED, verbose=0)
    bor.fit(x.values, y.values)
    kept = x.columns[bor.support_ | bor.support_weak_] if not bor.support_.any() else x.columns[bor.support_]
    if len(kept) == 0:
        return list(x.columns)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        en = _en().fit(x[kept], y)
    coef = en[-1].coef_[0]
    chosen = list(kept[np.abs(coef) > 0])
    return chosen or list(kept)


def select_consistent(x: pd.DataFrame, y: pd.Series, study: pd.Series, n_max: int = 40) -> list[str]:
    """Meta-analytic selection on the training studies only: standardised SCZ-HC difference per study,
    Stouffer-combined (per-study z capped at 3); keep features whose direction agrees in every training
    study (all but one when there are 4 or more),
    then the n_max strongest. Favours signals that replicate across cohorts over cohort-specific ones."""
    zs, signs = [], []
    for s in pd.unique(study):
        m = (study == s).values
        a, b = x[m & (y == 1).values], x[m & (y == 0).values]
        if len(a) < 3 or len(b) < 3:
            continue
        sd = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2)).replace(0, np.nan)
        d = (a.mean() - b.mean()) / sd
        zs.append(d / np.sqrt(1 / len(a) + 1 / len(b)))
        signs.append(np.sign(d))
    z = pd.concat(zs, axis=1).clip(-3, 3)  # one cohort cannot carry a feature on its own
    k = z.shape[1]
    stouffer = (z.sum(axis=1) / np.sqrt(k)).fillna(0)
    agree = (pd.concat(signs, axis=1).eq(np.sign(stouffer), axis=0)).sum(axis=1)
    need = k if k <= 3 else k - 1  # with 3 training studies (LOSO) all must agree
    ok = stouffer[(agree >= need) & (stouffer.abs() > 1.96)]
    pick = ok if len(ok) else stouffer[agree >= need] if (agree >= need).any() else stouffer
    return list(pick.abs().sort_values(ascending=False).index[:n_max])


def balanced_weights(y: pd.Series, study: pd.Series) -> np.ndarray:
    """Every study x group cell gets the same total weight (mean 1), so study identity carries no label
    information in training (Thirion is 2:1 HC:SCZ, the others about 1:1)."""
    cell = study.astype(str).values + "/" + y.astype(str).values
    counts = pd.Series(cell).value_counts()
    w = 1.0 / counts.reindex(cell).values
    return w * len(w) / w.sum()


def fit_models(x: pd.DataFrame, y: pd.Series, grids=FULL, sample_weight=None) -> dict:
    sw = {} if sample_weight is None else {"sample_weight": sample_weight}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rf = RandomForestClassifier(n_estimators=200, class_weight=None if sw else "balanced_subsample",
                                    max_depth=10, random_state=SEED, n_jobs=-1).fit(x, y, **sw)
        xgb = GridSearchCV(XGBClassifier(eval_metric="logloss", random_state=SEED, n_jobs=1), grids["xgb"],
                           cv=3, scoring="roc_auc", n_jobs=-1).fit(x, y, **sw).best_estimator_
        cat = GridSearchCV(CatBoostClassifier(verbose=0, random_seed=SEED, allow_writing_files=False, thread_count=1),
                           grids["cat"], cv=3, scoring="roc_auc", n_jobs=-1).fit(x, y, **sw).best_estimator_
        en = _en(cv=3).fit(x, y, **({"logisticregressioncv__sample_weight": sample_weight} if sw else {}))
    return {"Random Forest": rf, "XGBoost": xgb, "CatBoost": cat, "ElasticNet": en}


def predict(models: dict, x: pd.DataFrame) -> dict[str, np.ndarray]:
    out = {name: m.predict_proba(x)[:, 1] for name, m in models.items()}
    out["Ensemble (mean RF+XGB+Cat)"] = np.mean([out[m] for m in BASE_MODELS], axis=0)
    return out
