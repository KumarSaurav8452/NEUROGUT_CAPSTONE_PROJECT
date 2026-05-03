"""
NEUROGUT -- Admin API
=======================
User management (admin role only).
"""

import uuid
import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User
from api.auth import require_role
from schemas.patient import UserResponse, UserInvite

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """List all users in the admin's hospital."""
    users = db.query(User).filter(
        User.hospital_id == admin.hospital_id
    ).order_by(User.created_at.desc()).all()
    return users


@router.post("/users/invite", response_model=UserResponse)
def invite_user(
    data: UserInvite,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Create a new user (invite) in the admin's hospital."""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    default_password = "neurogut2025"

    new_user = User(
        id=str(uuid.uuid4()),
        hospital_id=admin.hospital_id,
        email=data.email,
        password_hash=_hash_password(default_password),
        role=data.role,
        full_name=data.full_name,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Enable/disable a user account."""
    target = db.query(User).filter(
        User.id == user_id,
        User.hospital_id == admin.hospital_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    target.is_active = not target.is_active
    db.commit()
    return {"id": target.id, "is_active": target.is_active}
