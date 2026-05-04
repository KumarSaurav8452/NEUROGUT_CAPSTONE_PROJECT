"""
NEUROGUT v2.0 -- Prediction API
===================================
POST /api/predict       -- single prediction with CI + alert trigger
POST /api/predict/batch -- batch CSV prediction
GET  /api/model/health  -- model health check
GET  /api/predictions/{id}
GET  /api/patients/{id}/trend -- longitudinal trend
GET  /api/benchmarks -- cohort benchmark stats
"""

import uuid
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import (
    User, MicrobiomeSample, Prediction, Patient, CohortBenchmark,
)
from api.auth import get_current_user
from schemas.prediction import (
    PredictionInput, PredictionOutput, BatchPredictionInput, ModelHealthResponse,
)
from services.predictor import predictor_service
from services.bootstrap_ci import compute_bootstrap_ci
from services.alert_service import check_and_create_alert
from services.audit_service import log_audit, AuditAction
from models.model_classes import FEATURE_NAMES

router = APIRouter(prefix="/api", tags=["Predictions"])


@router.post("/predict", response_model=PredictionOutput)
def predict_single(
    input_data: PredictionInput,
    request: Request,
    sample_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run GutMicrobiomeStacker on a single 13-feature sample with CI."""
    if not predictor_service.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")

    features = input_data.to_feature_list()
    result = predictor_service.predict(features)

    # v2.0: Compute bootstrap confidence intervals
    ci = {}
    try:
        ci = compute_bootstrap_ci(
            predictor_service.model,
            predictor_service.scaler_obj,
            np.array(features),
            n_iterations=100,
        )
    except Exception:
        ci = {
            "depression_ci_low": result["depression_prob"] - 0.05,
            "depression_ci_high": result["depression_prob"] + 0.05,
            "anxiety_ci_low": result["anxiety_prob"] - 0.05,
            "anxiety_ci_high": result["anxiety_prob"] + 0.05,
            "bootstrap_iterations": 0,
        }

    # Merge CI into result
    result.update(ci)

    # If no sample_id provided, create a transient one
    if not sample_id:
        sample_id = str(uuid.uuid4())

    # Save prediction to DB
    prediction_id = str(uuid.uuid4())
    pred_record = Prediction(
        id=prediction_id,
        sample_id=sample_id,
        model_version=result["model_version"],
        depression_prob=result["depression_prob"],
        anxiety_prob=result["anxiety_prob"],
        depression_label=result["depression_label"],
        anxiety_label=result["anxiety_label"],
        risk_tier=result["risk_tier"],
        rf_importances_json=result["rf_importances"],
        xgb_importances_json=result["xgb_importances"],
        consensus_features_json=result["consensus_features"],
        processing_time_ms=result["processing_time_ms"],
        depression_ci_low=ci.get("depression_ci_low"),
        depression_ci_high=ci.get("depression_ci_high"),
        anxiety_ci_low=ci.get("anxiety_ci_low"),
        anxiety_ci_high=ci.get("anxiety_ci_high"),
        bootstrap_iterations=ci.get("bootstrap_iterations", 100),
    )

    try:
        db.add(pred_record)
        db.commit()
        db.refresh(pred_record)

        # v2.0: Auto-trigger alert if high risk
        check_and_create_alert(db, pred_record)

        # v2.0: Audit log
        log_audit(
            db, user.id, AuditAction.PREDICTION_RUN,
            resource_type="prediction", resource_id=prediction_id,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        db.rollback()

    return PredictionOutput(
        prediction_id=prediction_id,
        sample_id=sample_id,
        **result,
    )


@router.post("/predict/batch", response_model=list[PredictionOutput])
def predict_batch(
    batch: BatchPredictionInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run predictions on multiple samples."""
    if not predictor_service.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")

    if user.role not in ("admin", "researcher"):
        raise HTTPException(status_code=403, detail="Batch prediction requires admin or researcher role")

    results = []
    for sample_input in batch.samples:
        features = sample_input.to_feature_list()
        result = predictor_service.predict(features)
        pred_id = str(uuid.uuid4())
        sample_id = str(uuid.uuid4())
        results.append(PredictionOutput(
            prediction_id=pred_id,
            sample_id=sample_id,
            **result,
        ))
    return results


@router.get("/model/health", response_model=ModelHealthResponse)
def model_health():
    """Check model status and stats."""
    return ModelHealthResponse(
        model_version=predictor_service.model_version,
        model_loaded=predictor_service.is_loaded,
        feature_count=len(FEATURE_NAMES),
        prediction_count=predictor_service.prediction_count,
        avg_latency_ms=round(predictor_service.avg_latency_ms, 2),
    )


@router.get("/predictions/{prediction_id}")
def get_prediction(
    prediction_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch a prediction by ID with full importances and CI."""
    pred = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")

    return {
        "id": pred.id,
        "sample_id": pred.sample_id,
        "model_version": pred.model_version,
        "depression_prob": pred.depression_prob,
        "anxiety_prob": pred.anxiety_prob,
        "depression_label": pred.depression_label,
        "anxiety_label": pred.anxiety_label,
        "risk_tier": pred.risk_tier,
        "rf_importances": pred.rf_importances_json,
        "xgb_importances": pred.xgb_importances_json,
        "consensus_features": pred.consensus_features_json,
        "processing_time_ms": pred.processing_time_ms,
        "depression_ci_low": pred.depression_ci_low,
        "depression_ci_high": pred.depression_ci_high,
        "anxiety_ci_low": pred.anxiety_ci_low,
        "anxiety_ci_high": pred.anxiety_ci_high,
        "created_at": pred.created_at,
    }


# -----------------------------------------------------------------------
# v2.0: Longitudinal Trend
# -----------------------------------------------------------------------
@router.get("/patients/{patient_id}/trend")
def patient_trend(
    patient_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return time-ordered array of analyses for longitudinal tracking."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")

    results = (
        db.query(MicrobiomeSample, Prediction)
        .join(Prediction, Prediction.sample_id == MicrobiomeSample.id)
        .filter(MicrobiomeSample.patient_id == patient_id)
        .order_by(MicrobiomeSample.collection_date.asc())
        .all()
    )

    trend = []
    for sample, pred in results:
        trend.append({
            "sample_date": sample.collection_date,
            "depression_prob": pred.depression_prob,
            "anxiety_prob": pred.anxiety_prob,
            "risk_tier": pred.risk_tier,
            "depression_ci_low": pred.depression_ci_low,
            "depression_ci_high": pred.depression_ci_high,
            "anxiety_ci_low": pred.anxiety_ci_low,
            "anxiety_ci_high": pred.anxiety_ci_high,
            "prediction_id": pred.id,
        })

    # Deterioration flag: 3 consecutive increases in depression_prob
    deteriorating = False
    if len(trend) >= 3:
        probs = [t["depression_prob"] for t in trend]
        for i in range(len(probs) - 2):
            if probs[i] < probs[i + 1] < probs[i + 2]:
                deteriorating = True
                break

    return {
        "patient_id": patient_id,
        "patient_code": patient.patient_code,
        "trend": trend,
        "total_analyses": len(trend),
        "deteriorating": deteriorating,
    }


# -----------------------------------------------------------------------
# v2.0: Cohort Benchmarks
# -----------------------------------------------------------------------
@router.get("/benchmarks")
def get_benchmarks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return cohort benchmark stats for all 13 taxa × 4 risk tiers."""
    benchmarks = db.query(CohortBenchmark).all()
    return [
        {
            "taxon_name": b.taxon_name,
            "risk_tier": b.risk_tier,
            "sample_count": b.sample_count,
            "mean_value": b.mean_value,
            "std_value": b.std_value,
            "p25_value": b.p25_value,
            "p50_value": b.p50_value,
            "p75_value": b.p75_value,
            "computed_at": b.computed_at.isoformat() if b.computed_at else None,
        }
        for b in benchmarks
    ]
