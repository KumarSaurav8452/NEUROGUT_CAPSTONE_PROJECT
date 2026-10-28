"""
NEUROGUT v4.0 -- Data Export API
===================================
GET /api/export  -- export anonymized cohort data as CSV or JSON

Exports joined microbiome_samples + predictions data with patient identifiers
stripped (anonymized sample IDs only). Supports filtering by risk_tier.
"""

import csv as csv_mod
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import MicrobiomeSample, Prediction, Patient
from api.auth import get_current_user, require_role
from services.audit_service import log_audit, AuditAction

router = APIRouter(prefix="/api", tags=["Export"])

# 13 bacterial taxa column names
TAXA_COLUMNS = [
    "lachnospira", "ruthenibacterium", "veillonella", "gardnerella",
    "pseudobutyrivibrio", "kocuria", "trueperella", "lancefieldella",
    "fructilactobacillus", "lachnoanaerobaculum", "corynebacterium",
    "raoultella", "lawsonella",
]


def _build_export_rows(db: Session, tier: str | None = None) -> list[dict]:
    """Query and build anonymized export rows."""
    query = (
        db.query(MicrobiomeSample, Prediction, Patient)
        .join(Prediction, Prediction.sample_id == MicrobiomeSample.id)
        .join(Patient, Patient.id == MicrobiomeSample.patient_id)
    )

    if tier:
        query = query.filter(Prediction.risk_tier == tier)

    query = query.order_by(MicrobiomeSample.created_at.desc())
    results = query.all()

    rows = []
    for sample, pred, patient in results:
        row = {
            "anonymized_id": patient.patient_code,
            "collection_date": sample.collection_date,
        }
        # Add 13 taxa values
        for taxon in TAXA_COLUMNS:
            row[taxon] = getattr(sample, taxon)

        # Add prediction results
        row["depression_prob"] = round(pred.depression_prob, 4)
        row["anxiety_prob"] = round(pred.anxiety_prob, 4)
        row["risk_tier"] = pred.risk_tier
        row["depression_ci_low"] = round(pred.depression_ci_low, 4) if pred.depression_ci_low is not None else None
        row["depression_ci_high"] = round(pred.depression_ci_high, 4) if pred.depression_ci_high is not None else None
        row["anxiety_ci_low"] = round(pred.anxiety_ci_low, 4) if pred.anxiety_ci_low is not None else None
        row["anxiety_ci_high"] = round(pred.anxiety_ci_high, 4) if pred.anxiety_ci_high is not None else None

        rows.append(row)

    return rows


@router.get("/export")
def export_dataset(
    request: Request,
    format: str = Query("csv", regex="^(csv|json)$"),
    tier: str | None = Query(None, description="Filter by risk tier"),
    db: Session = Depends(get_db),
    user=Depends(require_role("researcher", "admin")),
):
    """
    Export anonymized cohort data. Researcher and admin roles only.

    - **format**: 'csv' or 'json'
    - **tier**: optional risk tier filter (healthy, depression_only, anxiety_only, comorbid)
    """
    rows = _build_export_rows(db, tier if tier else None)

    # Audit log
    log_audit(
        db, user.id, AuditAction.DATA_EXPORT,
        resource_type="dataset",
        resource_id=f"{len(rows)}_rows_{format}",
        ip_address=request.client.host if request.client else None,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tier_suffix = f"_{tier}" if tier else ""

    if format == "json":
        content = json.dumps(rows, indent=2, default=str)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="neurogut_export{tier_suffix}_{timestamp}.json"'
            },
        )

    # CSV format (default)
    if not rows:
        # Return empty CSV with headers only
        headers = ["anonymized_id", "collection_date"] + TAXA_COLUMNS + [
            "depression_prob", "anxiety_prob", "risk_tier",
            "depression_ci_low", "depression_ci_high",
            "anxiety_ci_low", "anxiety_ci_high",
        ]
        output = io.StringIO()
        writer = csv_mod.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        output.seek(0)
    else:
        output = io.StringIO()
        fieldnames = list(rows[0].keys())
        writer = csv_mod.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="neurogut_export{tier_suffix}_{timestamp}.csv"'
        },
    )
