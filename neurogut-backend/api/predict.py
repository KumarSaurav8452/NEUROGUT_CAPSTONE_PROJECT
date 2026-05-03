"""
NEUROGUT -- Prediction API
=============================
POST /api/predict       -- single sample prediction
POST /api/predict/batch -- batch CSV prediction
GET  /api/model/health  -- model health check
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, MicrobiomeSample, Prediction
from api.auth import get_current_user
from schemas.prediction import (
    PredictionInput, PredictionOutput, BatchPredictionInput, ModelHealthResponse,
)
from services.predictor import predictor_service
from models.model_classes import FEATURE_NAMES

router = APIRouter(prefix="/api", tags=["Predictions"])


@router.post("/predict", response_model=PredictionOutput)
def predict_single(
    input_data: PredictionInput,
    sample_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run GutMicrobiomeStacker on a single 13-feature sample."""
    if not predictor_service.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")

    features = input_data.to_feature_list()
    result = predictor_service.predict(features)

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
    )

    try:
        db.add(pred_record)
        db.commit()
    except Exception:
        db.rollback()
        # Still return prediction even if DB save fails
        pass

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
    """Fetch a prediction by ID with full importances."""
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
        "created_at": pred.created_at,
    }
