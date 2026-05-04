"""
NEUROGUT v2.0 -- Alerts API
==============================
GET /api/alerts — list alerts (paginated, filterable)
PATCH /api/alerts/{id}/resolve — resolve an alert with notes
GET /api/alerts/count — unread alert count for badge
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.database import get_db
from db.models import User, Alert, Patient, Prediction
from api.auth import get_current_user
from services.audit_service import log_audit, AuditAction

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


class AlertResponse(BaseModel):
    id: str
    prediction_id: str
    patient_id: str
    patient_code: str | None = None
    triggered_by_rule: str
    status: str
    resolved_by: str | None = None
    resolved_at: str | None = None
    notes: str = ""
    depression_prob: float | None = None
    anxiety_prob: float | None = None
    risk_tier: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class ResolveRequest(BaseModel):
    notes: str = ""


class AlertCountResponse(BaseModel):
    unread: int
    total: int


@router.get("/count", response_model=AlertCountResponse)
def alert_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get unread and total alert counts."""
    base = db.query(Alert).join(Patient).filter(
        Patient.hospital_id == user.hospital_id
    )
    total = base.count()
    unread = base.filter(Alert.status == "unread").count()
    return AlertCountResponse(unread=unread, total=total)


@router.get("/", response_model=list[AlertResponse])
def list_alerts(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List alerts for the current user's hospital."""
    q = (
        db.query(Alert, Patient.patient_code, Prediction)
        .join(Patient, Alert.patient_id == Patient.id)
        .join(Prediction, Alert.prediction_id == Prediction.id)
        .filter(Patient.hospital_id == user.hospital_id)
    )
    if status:
        q = q.filter(Alert.status == status)

    q = q.order_by(Alert.created_at.desc())
    results = q.offset((page - 1) * page_size).limit(page_size).all()

    return [
        AlertResponse(
            id=a.id,
            prediction_id=a.prediction_id,
            patient_id=a.patient_id,
            patient_code=pc,
            triggered_by_rule=a.triggered_by_rule,
            status=a.status,
            resolved_by=a.resolved_by,
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
            notes=a.notes or "",
            depression_prob=p.depression_prob,
            anxiety_prob=p.anxiety_prob,
            risk_tier=p.risk_tier,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a, pc, p in results
    ]


@router.patch("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    req: ResolveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark an alert as resolved with optional notes."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")

    alert.status = "resolved"
    alert.resolved_by = user.id
    alert.resolved_at = datetime.now(timezone.utc)
    alert.notes = req.notes
    db.commit()

    log_audit(db, user.id, AuditAction.SETTINGS_CHANGE,
              resource_type="alert", resource_id=alert_id)

    return {"id": alert_id, "status": "resolved"}
