"""
NEUROGUT -- Model Export Script
================================
Train the GutMicrobiomeStacker (RF + XGB Chain + LR Meta-Learner)
on X_resampled.csv / y_resampled.csv, evaluate via cross-validation,
and export:
    - stacker.pkl   (trained model)
    - scaler.pkl    (StandardScaler fitted on training data)
    - model_card.json (version, metrics, feature list, limitations)

Usage:
    python neurogut-backend/models/export_model.py
"""

import sys
import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import (
    classification_report,
    hamming_loss,
    roc_auc_score,
    f1_score,
    accuracy_score,
)

warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# Ensure the models package is importable when running as script
# ---------------------------------------------------------------------------
_this_dir = Path(__file__).resolve().parent
_backend_dir = _this_dir.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from models.model_classes import (
    GutMicrobiomeStacker,
    SimpleClassifierChain,
    FEATURE_NAMES,
    _make_xgb,
    risk_tier,
)

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # c:\Major_project_Neuro_Gut
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = _this_dir


# ---------------------------------------------------------------------------
# MultilabelStratifiedKFold (simple manual version)
# ---------------------------------------------------------------------------
def multilabel_stratified_kfold(y, n_splits=5, random_state=42):
    """Create stratified folds based on the combined label pattern."""
    combined = y[:, 0] * 2 + y[:, 1]  # 0=healthy, 1=anx_only, 2=dep_only, 3=comorbid
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    return list(skf.split(np.zeros(len(y)), combined))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("NEUROGUT -- GutMicrobiomeStacker Export Pipeline")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    print("\n[1/6] Loading data...")
    X = pd.read_csv(DATA_DIR / "X_resampled.csv")
    y = pd.read_csv(DATA_DIR / "y_resampled.csv").values

    assert list(X.columns) == FEATURE_NAMES, (
        f"Feature mismatch: expected {FEATURE_NAMES}, got {list(X.columns)}"
    )
    print(f"  Loaded {X.shape[0]} samples x {X.shape[1]} features")
    print(f"  Labels: Depression={y[:, 0].sum():.0f} | Anxiety={y[:, 1].sum():.0f}")

    # ------------------------------------------------------------------
    # 2. Scale features
    # ------------------------------------------------------------------
    print("\n[2/6] Fitting StandardScaler...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"  Scaler fitted -- mean range [{scaler.mean_.min():.2f}, {scaler.mean_.max():.2f}]")

    # ------------------------------------------------------------------
    # 3. Cross-validation
    # ------------------------------------------------------------------
    print("\n[3/6] Running 5-fold MultilabelStratified cross-validation...")
    folds = multilabel_stratified_kfold(y, n_splits=5, random_state=42)

    cv_results = {
        "dep_auc": [],
        "anx_auc": [],
        "dep_f1": [],
        "anx_f1": [],
        "hamming": [],
        "accuracy_dep": [],
        "accuracy_anx": [],
    }

    for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
        X_tr, X_val = X_scaled[train_idx], X_scaled[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        # Build fresh stacker for this fold
        rf = MultiOutputClassifier(
            RandomForestClassifier(n_estimators=100, random_state=42)
        )
        xgb_chain = SimpleClassifierChain(_make_xgb, order=[0, 1])
        fold_stacker = GutMicrobiomeStacker(rf, xgb_chain)
        fold_stacker.fit(X_tr, y_tr)

        y_pred = fold_stacker.predict(X_val)
        y_proba = fold_stacker.predict_proba_final(X_val)

        # Metrics
        dep_auc = roc_auc_score(y_val[:, 0], y_proba[:, 0])
        anx_auc = roc_auc_score(y_val[:, 1], y_proba[:, 1]) if len(np.unique(y_val[:, 1])) > 1 else 0.5
        dep_f1 = f1_score(y_val[:, 0], y_pred[:, 0], zero_division=0)
        anx_f1 = f1_score(y_val[:, 1], y_pred[:, 1], zero_division=0)
        hl = hamming_loss(y_val, y_pred)

        cv_results["dep_auc"].append(dep_auc)
        cv_results["anx_auc"].append(anx_auc)
        cv_results["dep_f1"].append(dep_f1)
        cv_results["anx_f1"].append(anx_f1)
        cv_results["hamming"].append(hl)
        cv_results["accuracy_dep"].append(accuracy_score(y_val[:, 0], y_pred[:, 0]))
        cv_results["accuracy_anx"].append(accuracy_score(y_val[:, 1], y_pred[:, 1]))

        print(
            f"  Fold {fold_idx}: Dep AUC={dep_auc:.3f}  Anx AUC={anx_auc:.3f}  "
            f"Dep F1={dep_f1:.3f}  Anx F1={anx_f1:.3f}  Hamming={hl:.3f}"
        )

    # Summary
    print("\n  === Cross-Validation Summary ===")
    for key in cv_results:
        vals = cv_results[key]
        print(f"  {key:>14s}: {np.mean(vals):.3f} +/- {np.std(vals):.3f}")

    # ------------------------------------------------------------------
    # 4. Train final model on ALL data
    # ------------------------------------------------------------------
    print("\n[4/6] Training final model on full dataset...")
    t0 = time.time()

    rf_final = MultiOutputClassifier(
        RandomForestClassifier(n_estimators=100, random_state=42)
    )
    xgb_final = SimpleClassifierChain(_make_xgb, order=[0, 1])
    stacker_final = GutMicrobiomeStacker(rf_final, xgb_final)
    stacker_final.fit(X_scaled, y)

    train_time = time.time() - t0
    print(f"  Training completed in {train_time:.2f}s")

    # Quick sanity: predict on training data
    y_train_pred = stacker_final.predict(X_scaled)
    y_train_proba = stacker_final.predict_proba_final(X_scaled)
    train_hl = hamming_loss(y, y_train_pred)
    train_dep_auc = roc_auc_score(y[:, 0], y_train_proba[:, 0])
    train_anx_auc = roc_auc_score(y[:, 1], y_train_proba[:, 1])
    print(f"  Training set -- Hamming: {train_hl:.4f}  Dep AUC: {train_dep_auc:.4f}  Anx AUC: {train_anx_auc:.4f}")

    # ------------------------------------------------------------------
    # 5. Extract feature importances
    # ------------------------------------------------------------------
    print("\n[5/6] Extracting feature importances...")
    rf_importances = np.mean(
        [est.feature_importances_ for est in stacker_final.rf.estimators_], axis=0
    )
    # XGB chain -- second estimator has 14 features (13 taxa + Depression_Context)
    xgb_raw = stacker_final.xgb.estimators_[1].feature_importances_
    xgb_importances = xgb_raw[:-1]  # drop Depression_Context

    rf_top5 = set(
        pd.Series(rf_importances, index=FEATURE_NAMES).nlargest(5).index
    )
    xgb_top5 = set(
        pd.Series(xgb_importances, index=FEATURE_NAMES).nlargest(5).index
    )
    consensus = sorted(rf_top5.intersection(xgb_top5))

    print(f"  RF Top-5:  {sorted(rf_top5)}")
    print(f"  XGB Top-5: {sorted(xgb_top5)}")
    print(f"  Consensus: {consensus}")

    # ------------------------------------------------------------------
    # 6. Export artifacts
    # ------------------------------------------------------------------
    print("\n[6/6] Exporting artifacts...")

    # stacker.pkl
    stacker_path = MODEL_DIR / "stacker.pkl"
    joblib.dump(stacker_final, stacker_path)
    stacker_size = stacker_path.stat().st_size
    print(f"  [OK] stacker.pkl  ({stacker_size / 1024:.1f} KB)")

    # scaler.pkl
    scaler_path = MODEL_DIR / "scaler.pkl"
    joblib.dump(scaler, scaler_path)
    scaler_size = scaler_path.stat().st_size
    print(f"  [OK] scaler.pkl   ({scaler_size / 1024:.1f} KB)")

    # model_card.json
    model_card = {
        "model_name": "GutMicrobiomeStacker",
        "version": "v1.0",
        "description": (
            "Multi-label stacked ensemble for predicting Depression and Anxiety "
            "from gut microbiome composition (13 bacterial taxa). Architecture: "
            "RF MultiOutput + XGB ClassifierChain (Depression->Anxiety) + LR Meta-Learner."
        ),
        "task": "Multi-label binary classification (Depression, Anxiety)",
        "features": FEATURE_NAMES,
        "feature_count": len(FEATURE_NAMES),
        "input_description": "13 bacterial taxa relative abundances (CLR-transformed or raw scaled values)",
        "output": {
            "depression_prob": "P(Depression) from meta-learner [0.0, 1.0]",
            "anxiety_prob": "P(Anxiety) from meta-learner [0.0, 1.0]",
            "depression_label": "0 or 1 (threshold 0.5)",
            "anxiety_label": "0 or 1 (threshold 0.5)",
            "risk_tier": "healthy | depression_only | anxiety_only | comorbid",
        },
        "architecture": {
            "base_model_1": "MultiOutputClassifier(RandomForestClassifier(n_estimators=100))",
            "base_model_2": "ClassifierChain(XGBClassifier, order=[Depression->Anxiety])",
            "meta_learner": "MultiOutputClassifier(LogisticRegression)",
            "innovation": "XGB chain uses Depression prediction as extra feature for Anxiety prediction",
        },
        "training_data": {
            "source": "SMOTE-Tomek resampled gut microbiome dataset",
            "samples": int(X.shape[0]),
            "class_distribution": {
                "healthy": int(((y[:, 0] == 0) & (y[:, 1] == 0)).sum()),
                "depression_only": int(((y[:, 0] == 1) & (y[:, 1] == 0)).sum()),
                "anxiety_only": int(((y[:, 0] == 0) & (y[:, 1] == 1)).sum()),
                "comorbid": int(((y[:, 0] == 1) & (y[:, 1] == 1)).sum()),
            },
        },
        "cross_validation": {
            "method": "5-fold MultilabelStratifiedKFold",
            "metrics": {
                metric: {
                    "mean": round(float(np.mean(vals)), 4),
                    "std": round(float(np.std(vals)), 4),
                }
                for metric, vals in cv_results.items()
            },
        },
        "feature_importances": {
            "rf_importances": {
                name: round(float(imp), 6) for name, imp in zip(FEATURE_NAMES, rf_importances)
            },
            "xgb_importances": {
                name: round(float(imp), 6) for name, imp in zip(FEATURE_NAMES, xgb_importances)
            },
            "rf_top5": sorted(rf_top5),
            "xgb_top5": sorted(xgb_top5),
            "consensus_biomarkers": consensus,
        },
        "risk_tier_logic": {
            "healthy": "depression_label=0 AND anxiety_label=0",
            "depression_only": "depression_label=1 AND anxiety_label=0",
            "anxiety_only": "depression_label=0 AND anxiety_label=1",
            "comorbid": "depression_label=1 AND anxiety_label=1",
        },
        "limitations": [
            "Training data limited to 111 SMOTE-resampled samples from a single cohort",
            "Features are CLR-transformed -- raw 16S counts must be transformed before input",
            "No external validation on independent clinical cohort yet",
            "Model does not flag out-of-distribution inputs automatically",
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_time_seconds": round(train_time, 2),
        "python_version": sys.version,
        "sklearn_version": __import__("sklearn").__version__,
        "xgboost_version": __import__("xgboost").__version__,
    }

    card_path = MODEL_DIR / "model_card.json"
    with open(card_path, "w", encoding="utf-8") as f:
        json.dump(model_card, f, indent=2, ensure_ascii=False)
    print(f"  [OK] model_card.json")

    # ------------------------------------------------------------------
    # Final Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPORT COMPLETE")
    print("=" * 70)
    print(f"  Model:    {stacker_path}")
    print(f"  Scaler:   {scaler_path}")
    print(f"  Card:     {card_path}")
    print(f"\n  CV Depression AUC: {np.mean(cv_results['dep_auc']):.3f} +/- {np.std(cv_results['dep_auc']):.3f}")
    print(f"  CV Anxiety AUC:    {np.mean(cv_results['anx_auc']):.3f} +/- {np.std(cv_results['anx_auc']):.3f}")
    print(f"  CV Hamming Loss:   {np.mean(cv_results['hamming']):.3f} +/- {np.std(cv_results['hamming']):.3f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
