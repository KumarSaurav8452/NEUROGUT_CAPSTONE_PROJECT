"""
NEUROGUT v2.0 -- Report API
==============================
Generate and download clinical PDF reports with v2.0 enhancements.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, Prediction, Report, MicrobiomeSample, Patient, CohortBenchmark
from api.auth import get_current_user
from schemas.patient import ReportGenerateRequest, ReportResponse
from services.pdf_generator_v2 import generate_report_pdf_v2, compute_report_hash
from services.storage import storage_service
from services.audit_service import log_audit, AuditAction

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    req: ReportGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a v2.0 PDF clinical report for a prediction."""
    pred = db.query(Prediction).filter(Prediction.id == req.prediction_id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")

    existing = db.query(Report).filter(Report.prediction_id == pred.id).first()
    if existing:
        return existing

    sample = db.query(MicrobiomeSample).filter(MicrobiomeSample.id == pred.sample_id).first()
    patient_info = {"patient_code": "N/A", "age": None, "sex": "N/A", "notes": ""}
    sample_data = {"collection_date": "N/A", "input_method": "N/A"}

    if sample:
        sample_data = {"collection_date": sample.collection_date, "input_method": sample.input_method}
        patient = db.query(Patient).filter(Patient.id == sample.patient_id).first()
        if patient:
            patient_info = {"patient_code": patient.patient_code, "age": patient.age,
                           "sex": patient.sex, "notes": patient.notes}

    prediction_data = {
        "prediction_id": pred.id,
        "depression_prob": pred.depression_prob, "anxiety_prob": pred.anxiety_prob,
        "depression_label": pred.depression_label, "anxiety_label": pred.anxiety_label,
        "risk_tier": pred.risk_tier,
        "rf_importances": pred.rf_importances_json or {},
        "xgb_importances": pred.xgb_importances_json or {},
        "consensus_features": pred.consensus_features_json or [],
        "model_version": pred.model_version,
        "depression_ci_low": pred.depression_ci_low,
        "depression_ci_high": pred.depression_ci_high,
        "anxiety_ci_low": pred.anxiety_ci_low,
        "anxiety_ci_high": pred.anxiety_ci_high,
        "bootstrap_iterations": pred.bootstrap_iterations,
    }

    # Longitudinal trend data
    trend_data = None
    if sample and sample.patient_id:
        trend_results = (
            db.query(MicrobiomeSample, Prediction)
            .join(Prediction, Prediction.sample_id == MicrobiomeSample.id)
            .filter(MicrobiomeSample.patient_id == sample.patient_id)
            .order_by(MicrobiomeSample.collection_date.asc())
            .all()
        )
        if len(trend_results) >= 2:
            trend_data = [{"sample_date": s.collection_date, "depression_prob": p.depression_prob,
                          "anxiety_prob": p.anxiety_prob, "risk_tier": p.risk_tier} for s, p in trend_results]

    # Cohort benchmark data
    benchmark_data = None
    benchmarks = db.query(CohortBenchmark).filter(CohortBenchmark.risk_tier == pred.risk_tier).all()
    if benchmarks and sample:
        taxa_map = {"lachnospira": "Lachnospira", "ruthenibacterium": "Ruthenibacterium",
                    "veillonella": "Veillonella", "gardnerella": "Gardnerella",
                    "pseudobutyrivibrio": "Pseudobutyrivibrio", "kocuria": "Kocuria",
                    "trueperella": "Trueperella", "lancefieldella": "Lancefieldella",
                    "fructilactobacillus": "Fructilactobacillus", "lachnoanaerobaculum": "Lachnoanaerobaculum",
                    "corynebacterium": "Corynebacterium", "raoultella": "Raoultella", "lawsonella": "Lawsonella"}
        benchmark_data = []
        for bm in benchmarks:
            col = bm.taxon_name.lower()
            patient_val = getattr(sample, col, 0) if hasattr(sample, col) else 0
            benchmark_data.append({"taxon": bm.taxon_name, "patient_value": patient_val,
                                  "mean": bm.mean_value, "p25": bm.p25_value,
                                  "p50": bm.p50_value, "p75": bm.p75_value})

    pdf_bytes = generate_report_pdf_v2(
        patient_info, prediction_data, sample_data,
        clinician_name=user.full_name or user.email,
        trend_data=trend_data, benchmark_data=benchmark_data,
    )

    report_hash = compute_report_hash(pdf_bytes)
    file_key = f"report_{pred.id}.pdf"
    file_path = storage_service.save(file_key, pdf_bytes)

    report = Report(
        id=str(uuid.uuid4()), prediction_id=pred.id, generated_by=user.id,
        file_path=file_path, file_key=file_key, report_version=2, report_hash=report_hash,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    log_audit(db, user.id, AuditAction.REPORT_GENERATE,
              resource_type="report", resource_id=report.id,
              ip_address=request.client.host if request.client else None)

    return report


@router.get("/{report_id}/download")
def download_report(report_id: str, token: str | None = None, db: Session = Depends(get_db)):
    """Download a generated PDF report. Auth via ?token=<jwt> query param."""
    from api.auth import decode_token
    if token:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        raise HTTPException(status_code=401, detail="Token required. Pass ?token=<jwt>.")

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not storage_service.exists(report.file_key):
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    return FileResponse(path=report.file_path, media_type="application/pdf",
                       filename=f"neurogut_report_{report.prediction_id[:8]}.pdf")


@router.get("/", response_model=list[ReportResponse])
def list_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """List all reports generated by the current user's hospital."""
    reports = db.query(Report).filter(
        Report.generated_by.in_(db.query(User.id).filter(User.hospital_id == user.hospital_id))
    ).order_by(Report.created_at.desc()).all()
    return reports
