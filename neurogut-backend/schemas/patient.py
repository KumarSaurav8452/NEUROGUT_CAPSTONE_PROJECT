"""
NEUROGUT -- Patient & Sample Schemas (Pydantic)
=================================================
v4.0: Added UserRoleUpdate, InviteAccept, extended UserResponse with status/invite fields.
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------
class PatientCreate(BaseModel):
    patient_code: str = Field(..., min_length=1, max_length=50)
    age: Optional[int] = Field(None, gt=0, lt=120)
    sex: str = Field("prefer_not_to_say", pattern="^(male|female|other|prefer_not_to_say)$")
    notes: str = ""


class PatientResponse(BaseModel):
    id: str
    hospital_id: str
    patient_code: str
    age: Optional[int]
    sex: str
    notes: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PatientListResponse(BaseModel):
    patients: list[PatientResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Sample
# ---------------------------------------------------------------------------
class SampleCreate(BaseModel):
    patient_id: str
    collection_date: str = Field(..., description="ISO date string YYYY-MM-DD")
    input_method: str = Field("manual", pattern="^(manual|csv_upload)$")
    lachnospira: float
    ruthenibacterium: float
    veillonella: float
    gardnerella: float
    pseudobutyrivibrio: float
    kocuria: float
    trueperella: float
    lancefieldella: float
    fructilactobacillus: float
    lachnoanaerobaculum: float
    corynebacterium: float
    raoultella: float
    lawsonella: float


class SampleResponse(BaseModel):
    id: str
    patient_id: str
    collection_date: str
    input_method: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str
    hospital_id: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    full_name: str
    is_active: bool
    hospital_id: str
    # v4.0: lifecycle fields
    status: str = "active"
    invite_expires_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserInvite(BaseModel):
    """Admin creates a new user via invite (v4.0: replaces old invite with token-based flow)."""
    email: str
    role: str = Field("clinician", pattern="^(admin|clinician|researcher)$")
    full_name: str = ""
    welcome_message: str = ""


class UserRoleUpdate(BaseModel):
    """Update a user's role."""
    role: str = Field(..., pattern="^(admin|clinician|researcher)$")


class InviteAccept(BaseModel):
    """New user accepts an invite and sets their password."""
    token: str
    password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
class ReportGenerateRequest(BaseModel):
    prediction_id: str


class ReportResponse(BaseModel):
    id: str
    prediction_id: str
    file_path: str
    report_version: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
