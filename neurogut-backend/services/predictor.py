"""
NEUROGUT -- ML Predictor Service
==================================
Loads stacker.pkl + scaler.pkl at startup, exposes predict() for inference.
"""

import time
import json
import numpy as np
import joblib
import pandas as pd
from pathlib import Path

from models.model_classes import (
    GutMicrobiomeStacker,
    SimpleClassifierChain,
    FEATURE_NAMES,
    risk_tier,
    _make_xgb,
)

_MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


class PredictorService:
    """Singleton-style service that loads and serves the GutMicrobiomeStacker."""

    def __init__(self):
        self.stacker = None
        self.scaler = None
        self.model_card = None
        self.prediction_count = 0
        self.total_latency_ms = 0.0

    def load(self):
        """Load model artifacts from disk. Called once at startup."""
        stacker_path = _MODEL_DIR / "stacker.pkl"
        scaler_path = _MODEL_DIR / "scaler.pkl"
        card_path = _MODEL_DIR / "model_card.json"

        self.stacker = joblib.load(stacker_path)
        self.scaler = joblib.load(scaler_path)

        if card_path.exists():
            with open(card_path, "r", encoding="utf-8") as f:
                self.model_card = json.load(f)

        print(f"[Predictor] Model loaded: {type(self.stacker).__name__}")
        print(f"[Predictor] Version: {self.model_card.get('version', 'unknown')}")

    @property
    def is_loaded(self) -> bool:
        return self.stacker is not None and self.scaler is not None

    @property
    def model(self):
        """Expose model for bootstrap CI computation."""
        return self.stacker

    @property
    def scaler_obj(self):
        """Expose scaler for bootstrap CI computation."""
        return self.scaler

    @property
    def model_version(self) -> str:
        if self.model_card:
            return self.model_card.get("version", "v1.0")
        return "v1.0"

    @property
    def avg_latency_ms(self) -> float:
        if self.prediction_count == 0:
            return 0.0
        return self.total_latency_ms / self.prediction_count

    def predict(self, features: list[float]) -> dict:
        """Run inference on a single sample.

        Args:
            features: List of 13 floats in FEATURE_NAMES order.

        Returns:
            dict with depression_prob, anxiety_prob, labels, risk_tier,
            rf_importances, xgb_importances, consensus_features, processing_time_ms.
        """
        assert self.is_loaded, "Model not loaded. Call load() first."
        assert len(features) == 13, f"Expected 13 features, got {len(features)}"

        t0 = time.perf_counter()

        # Scale input
        X_raw = np.array([features], dtype=np.float64)
        X_scaled = self.scaler.transform(X_raw)

        # Predict
        labels = self.stacker.predict(X_scaled)[0]  # [dep_label, anx_label]
        probas = self.stacker.predict_proba_final(X_scaled)[0]  # [dep_prob, anx_prob]

        dep_label = int(labels[0])
        anx_label = int(labels[1])
        dep_prob = float(probas[0])
        anx_prob = float(probas[1])
        tier = risk_tier(dep_label, anx_label)

        # Feature importances
        rf_importances = {}
        xgb_importances = {}
        consensus = []

        try:
            rf_imp = np.mean(
                [est.feature_importances_ for est in self.stacker.rf.estimators_],
                axis=0,
            )
            rf_importances = {
                name: round(float(imp), 6) for name, imp in zip(FEATURE_NAMES, rf_imp)
            }

            xgb_raw = self.stacker.xgb.estimators_[1].feature_importances_
            xgb_imp = xgb_raw[:-1]  # drop Depression_Context
            xgb_importances = {
                name: round(float(imp), 6) for name, imp in zip(FEATURE_NAMES, xgb_imp)
            }

            rf_top5 = set(pd.Series(rf_imp, index=FEATURE_NAMES).nlargest(5).index)
            xgb_top5 = set(pd.Series(xgb_imp, index=FEATURE_NAMES).nlargest(5).index)
            consensus = sorted(rf_top5.intersection(xgb_top5))
        except Exception:
            pass  # importances are optional

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        self.prediction_count += 1
        self.total_latency_ms += elapsed_ms

        return {
            "depression_prob": dep_prob,
            "anxiety_prob": anx_prob,
            "depression_label": dep_label,
            "anxiety_label": anx_label,
            "risk_tier": tier,
            "rf_importances": rf_importances,
            "xgb_importances": xgb_importances,
            "consensus_features": consensus,
            "processing_time_ms": elapsed_ms,
            "model_version": self.model_version,
        }

    def predict_batch(self, feature_matrix: list[list[float]]) -> list[dict]:
        """Run inference on multiple samples."""
        return [self.predict(row) for row in feature_matrix]


# Module-level singleton
predictor_service = PredictorService()
