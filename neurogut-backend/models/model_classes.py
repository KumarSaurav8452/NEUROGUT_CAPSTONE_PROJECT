"""
NEUROGUT — Model Class Definitions
====================================
Shared module containing GutMicrobiomeStacker, SimpleClassifierChain,
and related classes. Imported by both export_model.py and the serving
layer (predictor.py) to ensure pickle compatibility.
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.multioutput import MultiOutputClassifier
from xgboost import XGBClassifier


# ---------------------------------------------------------------------------
# Feature names (canonical order)
# ---------------------------------------------------------------------------
FEATURE_NAMES = [
    "Lachnospira",
    "Ruthenibacterium",
    "Veillonella",
    "Gardnerella",
    "Pseudobutyrivibrio",
    "Kocuria",
    "Trueperella",
    "Lancefieldella",
    "Fructilactobacillus",
    "Lachnoanaerobaculum",
    "Corynebacterium",
    "Raoultella",
    "Lawsonella",
]


def _make_xgb():
    """Factory function for XGBClassifier (module-level for pickling)."""
    return XGBClassifier(
        eval_metric="logloss", random_state=42, use_label_encoder=False
    )


# ---------------------------------------------------------------------------
# ClassifierChain
# ---------------------------------------------------------------------------
class SimpleClassifierChain:
    """Minimal ClassifierChain that models label dependency.

    Trains estimators in *order*. The second estimator receives the
    first label's prediction as an extra feature (Depression_Context).
    This mirrors sklearn's ClassifierChain but keeps the XGB estimators
    directly accessible for feature-importance extraction.
    """

    def __init__(self, base_estimator_factory, order=None):
        self.base_factory = base_estimator_factory
        self.order = order or [0, 1]
        self.estimators_ = []

    def fit(self, X, y):
        self.estimators_ = []
        X_aug = np.array(X, dtype=np.float64)
        y = np.array(y)
        for i, label_idx in enumerate(self.order):
            est = self.base_factory()
            if i == 0:
                est.fit(X_aug, y[:, label_idx])
            else:
                # augment X with previous label's prediction
                prev_pred = self.estimators_[-1].predict(
                    X_aug[:, : X.shape[1]] if i > 1 else X_aug
                )
                X_chain = np.column_stack([X_aug[:, : X.shape[1]], prev_pred])
                est.fit(X_chain, y[:, label_idx])
            self.estimators_.append(est)
        return self

    def predict(self, X):
        X = np.array(X, dtype=np.float64)
        preds = []
        for i, est in enumerate(self.estimators_):
            if i == 0:
                p = est.predict(X)
            else:
                X_chain = np.column_stack([X, preds[-1]])
                p = est.predict(X_chain)
            preds.append(p)
        # Reorder back to original label order
        result = np.zeros((X.shape[0], len(self.order)), dtype=int)
        for out_idx, label_idx in enumerate(self.order):
            result[:, label_idx] = preds[out_idx]
        return result

    def predict_proba(self, X):
        X = np.array(X, dtype=np.float64)
        probas = []
        preds = []
        for i, est in enumerate(self.estimators_):
            if i == 0:
                p = est.predict_proba(X)[:, 1]
                pred = est.predict(X)
            else:
                X_chain = np.column_stack([X, preds[-1]])
                p = est.predict_proba(X_chain)[:, 1]
                pred = est.predict(X_chain)
            probas.append(p)
            preds.append(pred)
        # Reorder
        result = np.zeros((X.shape[0], len(self.order)))
        for out_idx, label_idx in enumerate(self.order):
            result[:, label_idx] = probas[out_idx]
        return result


# ---------------------------------------------------------------------------
# GutMicrobiomeStacker
# ---------------------------------------------------------------------------
class GutMicrobiomeStacker:
    """Custom probabilistic ensemble stacking RF + XGB Chain.

    Architecture:
        - Base 1: MultiOutputClassifier(RandomForestClassifier)
        - Base 2: ClassifierChain(XGBClassifier) with order [0,1]
                   (Depression -> Anxiety, with Depression_Context feature)
        - Meta:   MultiOutputClassifier(LogisticRegression)

    The meta-learner receives 4 probability features:
        [RF_P(Depression), RF_P(Anxiety), XGB_P(Depression), XGB_P(Anxiety)]
    """

    def __init__(self, rf_base, xgb_chain_base):
        self.rf = rf_base
        self.xgb = xgb_chain_base
        self.meta_learner = MultiOutputClassifier(
            LogisticRegression(max_iter=1000, random_state=42)
        )

    def fit(self, X, y):
        X = np.array(X, dtype=np.float64)
        y = np.array(y)
        # 1. Train base models
        self.rf.fit(X, y)
        self.xgb.fit(X, y)

        # 2. Generate meta-features (probabilities from each base)
        rf_probs = np.array(
            [est.predict_proba(X)[:, 1] for est in self.rf.estimators_]
        ).T  # shape (n, 2)
        xgb_probs = self.xgb.predict_proba(X)  # shape (n, 2)

        X_meta = np.hstack([rf_probs, xgb_probs])
        self.meta_learner.fit(X_meta, y)
        return self

    def predict_proba(self, X):
        """Return meta-feature matrix [RF_dep, RF_anx, XGB_dep, XGB_anx]."""
        X = np.array(X, dtype=np.float64)
        rf_probs = np.array(
            [est.predict_proba(X)[:, 1] for est in self.rf.estimators_]
        ).T
        xgb_probs = self.xgb.predict_proba(X)
        return np.hstack([rf_probs, xgb_probs])

    def predict_proba_final(self, X):
        """Return final calibrated [P(Depression), P(Anxiety)] from meta-learner."""
        X_meta = self.predict_proba(X)
        probs = []
        for est in self.meta_learner.estimators_:
            probs.append(est.predict_proba(X_meta)[:, 1])
        return np.column_stack(probs)

    def predict(self, X):
        X_meta = self.predict_proba(X)
        return self.meta_learner.predict(X_meta)


# ---------------------------------------------------------------------------
# Utility: compute risk tier
# ---------------------------------------------------------------------------
def risk_tier(dep_label: int, anx_label: int) -> str:
    """Classify prediction into risk tier."""
    if dep_label == 1 and anx_label == 1:
        return "comorbid"
    elif dep_label == 1:
        return "depression_only"
    elif anx_label == 1:
        return "anxiety_only"
    else:
        return "healthy"
