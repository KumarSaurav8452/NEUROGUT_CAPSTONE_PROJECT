"""
NEUROGUT v2.0 -- Bootstrap Confidence Interval Service
========================================================
Computes 95% CI via bootstrap resampling of the stacked ensemble.
"""

import numpy as np


def compute_bootstrap_ci(
    model,
    scaler,
    features: np.ndarray,
    n_iterations: int = 100,
    ci_level: float = 0.95,
    seed: int = 42,
) -> dict:
    """Compute confidence intervals for depression and anxiety probabilities.

    Uses bootstrap-style perturbation: adds small Gaussian noise to the input
    features and re-runs the ensemble to estimate prediction uncertainty.

    Args:
        model: Trained GutMicrobiomeStacker
        scaler: Fitted StandardScaler
        features: 1D array of 13 taxa values (raw, pre-scaling)
        n_iterations: Number of bootstrap iterations (default 100)
        ci_level: Confidence level (default 0.95 for 95% CI)
        seed: Random seed for reproducibility

    Returns:
        dict with depression_ci_low/high, anxiety_ci_low/high
    """
    rng = np.random.RandomState(seed)
    alpha = (1 - ci_level) / 2

    # Get the scaled standard deviations for noise calibration
    feature_stds = scaler.scale_ if hasattr(scaler, 'scale_') else np.ones(features.shape[0]) * 0.1

    dep_probs = []
    anx_probs = []

    for _ in range(n_iterations):
        # Add small Gaussian noise (5% of feature std) to simulate sampling uncertainty
        noise = rng.normal(0, feature_stds * 0.05, size=features.shape)
        perturbed = features + noise

        # Scale and predict
        X_scaled = scaler.transform(perturbed.reshape(1, -1))
        proba = model.predict_proba(X_scaled)

        dep_probs.append(float(proba[0, 0]))
        anx_probs.append(float(proba[0, 1]))

    dep_probs = np.array(dep_probs)
    anx_probs = np.array(anx_probs)

    return {
        "depression_ci_low": float(np.percentile(dep_probs, alpha * 100)),
        "depression_ci_high": float(np.percentile(dep_probs, (1 - alpha) * 100)),
        "anxiety_ci_low": float(np.percentile(anx_probs, alpha * 100)),
        "anxiety_ci_high": float(np.percentile(anx_probs, (1 - alpha) * 100)),
        "bootstrap_iterations": n_iterations,
    }
