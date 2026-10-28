"""
NEUROGUT v2 -- Parkinson's & schizophrenia prediction API
===========================================================
GET  /api/v2/models                    -- deploy models, their taxa and validation metrics
GET  /api/v2/templates/{disease}       -- CSV template (patient_code + model taxa, values in %)
POST /api/v2/predict                   -- one sample from typed values
POST /api/v2/predict/csv               -- CSV of model taxa (one row per sample) or a MetaPhlAn profile table
GET  /api/v2/predictions               -- history (filter by disease / patient)
GET  /api/v2/predictions/{id}
"""

from __future__ import annotations

import csv
import io
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, Patient, V2Prediction
from api.auth import get_current_user
from services.audit_service import log_audit, AuditAction
from services.predictor_v2 import predictor_v2, DISEASES

router = APIRouter(prefix="/api/v2", tags=["Predictions v2 (PD / SCZ)"])
MAX_ROWS = 500


class V2Input(BaseModel):
    disease: str = Field(pattern="^(scz|pd)$")
    patient_id: str | None = None
    sample_label: str = ""
    collection_date: str | None = None
    abundances: dict[str, float]


def _bundle_or_404(disease: str):
    if disease not in DISEASES:
        raise HTTPException(400, "disease must be 'scz' or 'pd'")
    try:
        return predictor_v2.get(disease)
    except KeyError:
        raise HTTPException(503, f"{disease} model not installed (models/v2/{disease}.joblib)")


def _patient(db: Session, user: User, patient_id: str | None = None, code: str | None = None) -> Patient | None:
    q = db.query(Patient).filter(Patient.hospital_id == user.hospital_id)
    if patient_id:
        p = q.filter(Patient.id == patient_id).first()
        if not p:
            raise HTTPException(404, "Patient not found")
        return p
    if code:
        return q.filter(Patient.patient_code == code).first()
    return None


def _save(db, user, disease, pct, missing, result, method, patient=None, label="", date=None) -> dict:
    row = V2Prediction(
        hospital_id=user.hospital_id, patient_id=patient.id if patient else None, submitted_by=user.id,
        disease=disease, sample_label=label or (patient.patient_code if patient else ""), collection_date=date,
        input_method=method, abundances_json={k.split("|")[-1]: v for k, v in pct.items()},
        probability=result["probability"], label=result["label"], risk_tier=result["risk_tier"],
        model_probs_json=result["model_probs"], drivers_json=result["drivers"], missing_taxa=missing,
        model_version=result["model_version"],
    )
    db.add(row)
    db.flush()
    return _out(row, patient)


def _out(row: V2Prediction, patient: Patient | None = None) -> dict:
    return {
        "id": row.id, "disease": row.disease, "patient_id": row.patient_id,
        "patient_code": patient.patient_code if patient else None, "sample_label": row.sample_label,
        "collection_date": row.collection_date, "input_method": row.input_method,
        "probability": row.probability, "label": row.label, "risk_tier": row.risk_tier,
        "model_probs": row.model_probs_json, "drivers": row.drivers_json, "missing_taxa": row.missing_taxa,
        "abundances": row.abundances_json, "model_version": row.model_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/models")
def models_info(user: User = Depends(get_current_user)):
    info = predictor_v2.info()
    if not info:
        raise HTTPException(503, "No v2 models installed in models/v2/")
    return info


@router.get("/templates/{disease}")
def template(disease: str, user: User = Depends(get_current_user)):
    b = _bundle_or_404(disease)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["patient_code", "collection_date", *[b["display"][f] for f in b["features"]]])
    w.writerow(["EXAMPLE-001", "2026-10-29", *[round(b["reference"][f]["healthy_median_pct"], 4) for f in b["features"]]])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=neurogut_v2_{disease}_template.csv"})


@router.post("/predict")
def predict(body: V2Input, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _bundle_or_404(body.disease)
    patient = _patient(db, user, body.patient_id)
    pct, missing = predictor_v2.from_named(body.disease, body.abundances)
    t0 = time.time()
    result = predictor_v2.predict(body.disease, pct)
    out = _save(db, user, body.disease, pct, missing, result, "manual", patient, body.sample_label, body.collection_date)
    log_audit(db, user.id, AuditAction.PREDICTION_RUN, resource_type="v2_prediction", resource_id=out["id"],
              ip_address=request.client.host if request.client else None)
    db.commit()
    out["processing_ms"] = int((time.time() - t0) * 1000)
    return out


@router.post("/predict/csv")
async def predict_csv(request: Request, disease: str = Form(...), file: UploadFile = File(...),
                      patient_id: str | None = Form(None),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _bundle_or_404(disease)
    content = await file.read()
    if not content.strip():
        raise HTTPException(400, "File is empty")
    try:
        kind, df = predictor_v2.read_upload(content)
    except Exception as e:  # noqa: BLE001 -- report any parse problem to the user
        raise HTTPException(400, f"Could not read file: {e}")
    fixed = _patient(db, user, patient_id) if patient_id else None
    results, errors = [], []
    if kind == "profile":
        samples = predictor_v2.from_profile(disease, df)
        if len(samples) > MAX_ROWS:
            raise HTTPException(400, f"At most {MAX_ROWS} samples per upload")
        for name, pct in samples.items():
            if sum(pct.values()) == 0:
                errors.append({"row": name, "error": "none of the model taxa found in this profile"})
                continue
            res = predictor_v2.predict(disease, pct)
            p = fixed or _patient(db, user, code=name)
            results.append(_save(db, user, disease, pct, 0, res, "profile_upload", p, name))
    else:
        if len(df) > MAX_ROWS:
            raise HTTPException(400, f"At most {MAX_ROWS} rows per upload")
        cols = {c.lower(): c for c in df.columns}
        code_col, date_col = cols.get("patient_code") or cols.get("sample_id"), cols.get("collection_date")
        for i, r in df.iterrows():
            values = {c: r[c] for c in df.columns if c not in (code_col, date_col)}
            try:
                values = {k: float(v) for k, v in values.items() if str(v).strip() != ""}
            except ValueError as e:
                errors.append({"row": int(i) + 2, "error": f"non-numeric value ({e})"})
                continue
            pct, missing = predictor_v2.from_named(disease, values)
            if missing == len(pct):
                errors.append({"row": int(i) + 2, "error": "no model taxa columns found (download the template)"})
                continue
            code = str(r[code_col]) if code_col else ""
            res = predictor_v2.predict(disease, pct)
            p = fixed or _patient(db, user, code=code)
            results.append(_save(db, user, disease, pct, missing, res, "csv_upload", p, code,
                                 str(r[date_col]) if date_col else None))
    log_audit(db, user.id, AuditAction.PREDICTION_RUN, resource_type="v2_prediction_batch",
              resource_id=f"{disease}:{len(results)}", ip_address=request.client.host if request.client else None)
    db.commit()
    return {"format": kind, "n_predicted": len(results), "results": results, "errors": errors}


@router.get("/predictions")
def history(disease: str | None = None, patient_id: str | None = None, limit: int = Query(100, le=500),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(V2Prediction).filter(V2Prediction.hospital_id == user.hospital_id)
    if disease:
        q = q.filter(V2Prediction.disease == disease)
    if patient_id:
        q = q.filter(V2Prediction.patient_id == patient_id)
    rows = q.order_by(V2Prediction.created_at.desc()).limit(limit).all()
    patients = {p.id: p for p in db.query(Patient).filter(Patient.id.in_({r.patient_id for r in rows if r.patient_id})).all()}
    return [_out(r, patients.get(r.patient_id)) for r in rows]


@router.get("/predictions/{prediction_id}")
def get_one(prediction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(V2Prediction).filter(V2Prediction.id == prediction_id,
                                        V2Prediction.hospital_id == user.hospital_id).first()
    if not row:
        raise HTTPException(404, "Prediction not found")
    patient = db.query(Patient).get(row.patient_id) if row.patient_id else None
    return _out(row, patient)
