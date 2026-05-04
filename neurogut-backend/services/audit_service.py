"""
NEUROGUT v2.0 -- Audit Logging Service
=========================================
Provides helper to create audit log entries + FastAPI middleware.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import AuditLog


# Action constants
class AuditAction:
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PATIENT_VIEW = "PATIENT_VIEW"
    SAMPLE_SUBMIT = "SAMPLE_SUBMIT"
    PREDICTION_RUN = "PREDICTION_RUN"
    REPORT_GENERATE = "REPORT_GENERATE"
    REPORT_DOWNLOAD = "REPORT_DOWNLOAD"
    USER_INVITE = "USER_INVITE"
    SETTINGS_CHANGE = "SETTINGS_CHANGE"
    DATA_EXPORT = "DATA_EXPORT"


def log_audit(
    db: Session,
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    """Create an audit log entry."""
    entry = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    db.commit()
    return entry


def log_audit_async(
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    """Fire-and-forget audit log (uses own DB session)."""
    try:
        db = SessionLocal()
        log_audit(db, user_id, action, resource_type, resource_id, ip_address, user_agent)
        db.close()
    except Exception:
        pass  # Audit must never break the main flow
