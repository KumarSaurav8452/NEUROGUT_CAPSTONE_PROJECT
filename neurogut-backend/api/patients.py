"""
NEUROGUT -- Patient & Sample CRUD API
========================================
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, Patient, MicrobiomeSample, Prediction
from api.auth import get_current_user
from schemas.patient import (
    PatientCreate, PatientResponse, PatientListResponse,
    SampleCreate, SampleResponse,
)

router = APIRouter(prefix="/api", tags=["Patients"])


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------
@router.post("/patients", response_model=PatientResponse)
def create_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Register a new patient (anonymized code)."""
    # Check duplicate within hospital
    existing = db.query(Patient).filter(
        Patient.hospital_id == user.hospital_id,
        Patient.patient_code == data.patient_code,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Patient code already exists in this hospital")

    patient = Patient(
        id=str(uuid.uuid4()),
        hospital_id=user.hospital_id,
        created_by=user.id,
        patient_code=data.patient_code,
        age=data.age,
        sex=data.sex,
        notes=data.notes,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/patients", response_model=PatientListResponse)
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="Search by patient code"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List patients in the user's hospital with pagination."""
    query = db.query(Patient).filter(Patient.hospital_id == user.hospital_id)
    if search:
        query = query.filter(Patient.patient_code.contains(search))

    total = query.count()
    patients = query.order_by(Patient.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PatientListResponse(
        patients=[PatientResponse.model_validate(p) for p in patients],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/patients/{patient_id}")
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get patient profile with all samples and predictions."""
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.hospital_id == user.hospital_id,
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    samples_data = []
    for sample in patient.samples:
        sample_dict = {
            "id": sample.id,
            "collection_date": sample.collection_date,
            "input_method": sample.input_method,
            "created_at": sample.created_at,
            "prediction": None,
        }
        if sample.prediction:
            p = sample.prediction
            sample_dict["prediction"] = {
                "id": p.id,
                "depression_prob": p.depression_prob,
                "anxiety_prob": p.anxiety_prob,
                "depression_label": p.depression_label,
                "anxiety_label": p.anxiety_label,
                "risk_tier": p.risk_tier,
                "created_at": p.created_at,
            }
        samples_data.append(sample_dict)

    return {
        "id": patient.id,
        "patient_code": patient.patient_code,
        "age": patient.age,
        "sex": patient.sex,
        "notes": patient.notes,
        "created_at": patient.created_at,
        "samples": samples_data,
    }


# ---------------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------------
@router.post("/samples", response_model=SampleResponse)
def submit_sample(
    data: SampleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit a microbiome sample for a patient."""
    # Verify patient exists and belongs to user's hospital
    patient = db.query(Patient).filter(
        Patient.id == data.patient_id,
        Patient.hospital_id == user.hospital_id,
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    sample = MicrobiomeSample(
        id=str(uuid.uuid4()),
        patient_id=data.patient_id,
        submitted_by=user.id,
        collection_date=data.collection_date,
        input_method=data.input_method,
        lachnospira=data.lachnospira,
        ruthenibacterium=data.ruthenibacterium,
        veillonella=data.veillonella,
        gardnerella=data.gardnerella,
        pseudobutyrivibrio=data.pseudobutyrivibrio,
        kocuria=data.kocuria,
        trueperella=data.trueperella,
        lancefieldella=data.lancefieldella,
        fructilactobacillus=data.fructilactobacillus,
        lachnoanaerobaculum=data.lachnoanaerobaculum,
        corynebacterium=data.corynebacterium,
        raoultella=data.raoultella,
        lawsonella=data.lawsonella,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample
