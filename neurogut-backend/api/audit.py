"""
NEUROGUT v2.0 -- Audit Log API
=================================
GET /api/audit — admin-only, paginated, filterable audit log.
"""

import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.database import get_db
from db.models import User, AuditLog
from api.auth import get_current_user, require_role

router = APIRouter(prefix="/api/audit", tags=["Audit"])


class AuditEntry(BaseModel):
    id: str
    user_id: str | None = None
    user_email: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[AuditEntry])
def list_audit_logs(
    action: str | None = None,
    user_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    format: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """List audit logs. Admin only. Supports CSV export via ?format=csv."""
    q = db.query(AuditLog, User.email).outerjoin(User, AuditLog.user_id == User.id)

    if action:
        q = q.filter(AuditLog.action == action)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)

    q = q.order_by(AuditLog.created_at.desc())

    # CSV export
    if format == "csv":
        all_rows = q.limit(10000).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "user_id", "user_email", "action", "resource_type", "resource_id", "ip_address", "created_at"])
        for log, email in all_rows:
            writer.writerow([log.id, log.user_id, email, log.action, log.resource_type, log.resource_id, log.ip_address,
                             log.created_at.isoformat() if log.created_at else ""])
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )

    results = q.offset((page - 1) * page_size).limit(page_size).all()
    return [
        AuditEntry(
            id=log.id,
            user_id=log.user_id,
            user_email=email,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            created_at=log.created_at.isoformat() if log.created_at else None,
        )
        for log, email in results
    ]
