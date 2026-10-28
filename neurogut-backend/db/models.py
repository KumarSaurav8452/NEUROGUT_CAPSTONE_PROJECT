"""
NEUROGUT -- ORM Models  (v2.0 / v4.0)
=======================================
Original 6 tables + 3 new v2.0 tables (AuditLog, Alert, CohortBenchmark).
Prediction table extended with confidence interval columns.
v4.0: User table extended with status, invite_token_hash, invite_expires_at.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Float, SmallInteger, Boolean, DateTime,
    ForeignKey, JSON, Integer, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from db.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# hospitals
# ---------------------------------------------------------------------------
class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    subdomain = Column(String(100), unique=True, nullable=False)
    logo_url = Column(Text, default="")
    settings_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now)

    users = relationship("User", back_populates="hospital", cascade="all, delete-orphan")
    patients = relationship("Patient", back_populates="hospital", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    hospital_id = Column(String(36), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(Text, nullable=True)   # nullable: invited users have no password yet
    role = Column(String(20), nullable=False)  # admin, clinician, researcher
    full_name = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    # v4.0: user lifecycle status
    status = Column(String(20), nullable=False, default="active")  # invited, active, deactivated
    invite_token_hash = Column(Text, nullable=True)   # bcrypt hash of raw invite token
    invite_expires_at = Column(DateTime, nullable=True)  # 72-hour expiry
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    hospital = relationship("Hospital", back_populates="users")
    patients_created = relationship("Patient", back_populates="created_by_user")
    samples_submitted = relationship("MicrobiomeSample", back_populates="submitted_by_user")
    reports_generated = relationship("Report", back_populates="generated_by_user")


# ---------------------------------------------------------------------------
# patients
# ---------------------------------------------------------------------------
class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("hospital_id", "patient_code", name="uq_hospital_patient"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    hospital_id = Column(String(36), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    patient_code = Column(String(50), nullable=False)
    age = Column(SmallInteger, nullable=True)
    sex = Column(String(20), default="prefer_not_to_say")  # male, female, other, prefer_not_to_say
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_now)

    hospital = relationship("Hospital", back_populates="patients")
    created_by_user = relationship("User", back_populates="patients_created")
    samples = relationship("MicrobiomeSample", back_populates="patient", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="patient", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# microbiome_samples
# ---------------------------------------------------------------------------
class MicrobiomeSample(Base):
    __tablename__ = "microbiome_samples"

    id = Column(String(36), primary_key=True, default=_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    submitted_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    collection_date = Column(String(10), nullable=False)  # ISO date string
    input_method = Column(String(20), nullable=False, default="manual")  # manual, csv_upload

    # 13 bacterial taxa -- float values
    lachnospira = Column(Float, nullable=False)
    ruthenibacterium = Column(Float, nullable=False)
    veillonella = Column(Float, nullable=False)
    gardnerella = Column(Float, nullable=False)
    pseudobutyrivibrio = Column(Float, nullable=False)
    kocuria = Column(Float, nullable=False)
    trueperella = Column(Float, nullable=False)
    lancefieldella = Column(Float, nullable=False)
    fructilactobacillus = Column(Float, nullable=False)
    lachnoanaerobaculum = Column(Float, nullable=False)
    corynebacterium = Column(Float, nullable=False)
    raoultella = Column(Float, nullable=False)
    lawsonella = Column(Float, nullable=False)

    created_at = Column(DateTime, default=_now)

    patient = relationship("Patient", back_populates="samples")
    submitted_by_user = relationship("User", back_populates="samples_submitted")
    prediction = relationship("Prediction", back_populates="sample", uselist=False, cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# predictions  (v2.0: added CI columns)
# ---------------------------------------------------------------------------
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String(36), primary_key=True, default=_uuid)
    sample_id = Column(String(36), ForeignKey("microbiome_samples.id", ondelete="CASCADE"), nullable=False)
    model_version = Column(String(50), nullable=False, default="v1.0")
    depression_prob = Column(Float, nullable=False)
    anxiety_prob = Column(Float, nullable=False)
    depression_label = Column(SmallInteger, nullable=False)
    anxiety_label = Column(SmallInteger, nullable=False)
    risk_tier = Column(String(30), nullable=False)  # healthy, depression_only, anxiety_only, comorbid
    rf_importances_json = Column(JSON, default=dict)
    xgb_importances_json = Column(JSON, default=dict)
    consensus_features_json = Column(JSON, default=list)
    processing_time_ms = Column(Integer, default=0)

    # v2.0: Confidence intervals (bootstrap)
    depression_ci_low = Column(Float, nullable=True)
    depression_ci_high = Column(Float, nullable=True)
    anxiety_ci_low = Column(Float, nullable=True)
    anxiety_ci_high = Column(Float, nullable=True)
    bootstrap_iterations = Column(SmallInteger, default=100)

    created_at = Column(DateTime, default=_now)

    sample = relationship("MicrobiomeSample", back_populates="prediction")
    report = relationship("Report", back_populates="prediction", uselist=False, cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="prediction", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# reports  (v2.0: added report_hash)
# ---------------------------------------------------------------------------
class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    prediction_id = Column(String(36), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False)
    generated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    file_path = Column(Text, nullable=False)  # local path (swap to s3_url later)
    file_key = Column(Text, nullable=False)   # storage key
    report_version = Column(SmallInteger, default=2)
    report_hash = Column(String(64), nullable=True)  # v2.0: SHA-256 of PDF content
    created_at = Column(DateTime, default=_now)

    prediction = relationship("Prediction", back_populates="report")
    generated_by_user = relationship("User", back_populates="reports_generated")


# ===========================================================================
# v2.0 NEW TABLES
# ===========================================================================

# ---------------------------------------------------------------------------
# audit_logs  (v2.0)
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(30), nullable=False)
    # LOGIN, LOGOUT, PATIENT_VIEW, SAMPLE_SUBMIT, PREDICTION_RUN,
    # REPORT_GENERATE, REPORT_DOWNLOAD, USER_INVITE, SETTINGS_CHANGE, DATA_EXPORT
    resource_type = Column(String(50), nullable=True)  # patient, prediction, report, user
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)

    user = relationship("User")


# ---------------------------------------------------------------------------
# alerts  (v2.0)
# ---------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    prediction_id = Column(String(36), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    triggered_by_rule = Column(String(100), nullable=False)  # comorbid_auto, high_risk_threshold
    status = Column(String(20), nullable=False, default="unread")  # unread, read, resolved, escalated
    resolved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_now)

    prediction = relationship("Prediction", back_populates="alerts")
    patient = relationship("Patient", back_populates="alerts")
    resolved_by_user = relationship("User")


# ---------------------------------------------------------------------------
# cohort_benchmarks  (v2.0)
# ---------------------------------------------------------------------------
class CohortBenchmark(Base):
    __tablename__ = "cohort_benchmarks"
    __table_args__ = (
        UniqueConstraint("taxon_name", "risk_tier", name="uq_taxon_tier"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    taxon_name = Column(String(100), nullable=False)
    risk_tier = Column(String(30), nullable=False)
    sample_count = Column(Integer, nullable=False, default=0)
    mean_value = Column(Float, nullable=False, default=0.0)
    std_value = Column(Float, nullable=False, default=0.0)
    p25_value = Column(Float, nullable=False, default=0.0)
    p50_value = Column(Float, nullable=False, default=0.0)
    p75_value = Column(Float, nullable=False, default=0.0)
    computed_at = Column(DateTime, default=_now)



# ---------------------------------------------------------------------------
# NeuroGut v2: Parkinson's / schizophrenia predictions (one table for both diseases)
# ---------------------------------------------------------------------------
class V2Prediction(Base):
    __tablename__ = "v2_predictions"

    id = Column(String(36), primary_key=True, default=_uuid)
    hospital_id = Column(String(36), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    submitted_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    disease = Column(String(10), nullable=False)          # scz, pd
    sample_label = Column(String(100), default="")         # patient code / sample name from the upload
    collection_date = Column(String(10), nullable=True)
    input_method = Column(String(20), nullable=False, default="manual")  # manual, csv_upload, profile_upload
    abundances_json = Column(JSON, default=dict)            # model taxa -> % relative abundance
    probability = Column(Float, nullable=False)
    label = Column(SmallInteger, nullable=False)            # 1 = disease-like profile
    risk_tier = Column(String(20), nullable=False)          # low, moderate, high
    model_probs_json = Column(JSON, default=dict)
    drivers_json = Column(JSON, default=list)
    missing_taxa = Column(SmallInteger, default=0)
    model_version = Column(String(30), nullable=False, default="v2.0-deploy")
    created_at = Column(DateTime, default=_now)
