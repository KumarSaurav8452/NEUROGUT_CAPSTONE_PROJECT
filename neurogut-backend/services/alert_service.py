"""
NEUROGUT v2.0 -- Alert Service
================================
Auto-triggers alerts for high-risk predictions and manages alert lifecycle.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from db.models import Alert, Prediction, MicrobiomeSample, Patient


# Default thresholds (configurable per hospital via settings_json)
DEFAULT_ALERT_RULES = {
    "comorbid_always_alert": True,
    "depression_threshold": 0.75,
    "anxiety_threshold": 0.75,
}


def check_and_create_alert(
    db: Session,
    prediction: Prediction,
    rules: dict | None = None,
) -> Alert | None:
    """Check if a prediction triggers an alert based on hospital rules.

    Returns the created Alert or None if no alert triggered.
    """
    rules = rules or DEFAULT_ALERT_RULES

    triggered_rule = None

    # Rule 1: Comorbid always alerts
    if rules.get("comorbid_always_alert") and prediction.risk_tier == "comorbid":
        triggered_rule = "comorbid_auto"

    # Rule 2: High depression probability
    elif prediction.depression_prob >= rules.get("depression_threshold", 0.75):
        triggered_rule = "high_risk_depression"

    # Rule 3: High anxiety probability
    elif prediction.anxiety_prob >= rules.get("anxiety_threshold", 0.75):
        triggered_rule = "high_risk_anxiety"

    if not triggered_rule:
        return None

    # Get patient_id from sample
    sample = db.query(MicrobiomeSample).filter(
        MicrobiomeSample.id == prediction.sample_id
    ).first()
    if not sample:
        return None

    alert = Alert(
        id=str(uuid.uuid4()),
        prediction_id=prediction.id,
        patient_id=sample.patient_id,
        triggered_by_rule=triggered_rule,
        status="unread",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_alert_rules(hospital_settings: dict) -> dict:
    """Extract alert rules from hospital settings JSON."""
    return hospital_settings.get("alert_rules", DEFAULT_ALERT_RULES)
