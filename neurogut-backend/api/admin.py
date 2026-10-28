"""
NEUROGUT -- Admin API (v4.0)
==============================
Full user lifecycle management:
  - List users (search, filter, paginate)
  - Create + invite user (token-based, email with magic link)
  - Update user role
  - Deactivate / activate user
  - Re-invite user (regenerate token)
  - Toggle user (legacy: kept for backward compat)
"""

import os
import uuid
import secrets
import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, AuditLog
from api.auth import require_role, get_current_user
from schemas.patient import UserResponse, UserInvite, UserRoleUpdate
from services.email import send_invite_email

router = APIRouter(prefix="/api/admin", tags=["Admin"])

INVITE_TOKEN_EXPIRE_HOURS = 72


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _generate_invite_token() -> str:
    """Generate a URL-safe 64-character random token."""
    return secrets.token_urlsafe(48)  # ~64 chars base64url


def _write_audit(db: Session, user_id: str, action: str, resource_type: str = None, resource_id: str = None):
    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(log)


# ---------------------------------------------------------------------------
# GET /api/admin/users
# ---------------------------------------------------------------------------
@router.get("/users", response_model=list[UserResponse])
def list_users(
    search: Optional[str] = Query(None, description="Filter by name or email"),
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """List all users in the admin's hospital with search/filter/pagination."""
    query = db.query(User).filter(User.hospital_id == admin.hospital_id)

    if search:
        like = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)

    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return users


# ---------------------------------------------------------------------------
# POST /api/admin/users  (Create + Invite)
# ---------------------------------------------------------------------------
@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    data: UserInvite,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Create a new user with status='invited' and send invitation email."""
    # Validate email uniqueness
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Generate invite token
    raw_token = _generate_invite_token()
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_TOKEN_EXPIRE_HOURS)

    new_user = User(
        id=str(uuid.uuid4()),
        hospital_id=admin.hospital_id,
        email=data.email,
        password_hash=None,           # No password until invite accepted
        role=data.role,
        full_name=data.full_name,
        is_active=True,
        status="invited",
        invite_token_hash=token_hash,
        invite_expires_at=expires_at,
    )
    db.add(new_user)

    # Audit log
    _write_audit(db, admin.id, "USER_INVITE", "user", new_user.id)
    db.commit()
    db.refresh(new_user)

    # Send invite email (non-blocking: failure doesn't roll back user creation)
    hospital_name = admin.hospital.name if admin.hospital else "Your Hospital"
    send_invite_email(
        to_email=data.email,
        to_name=data.full_name or data.email.split("@")[0],
        inviter_name=admin.full_name or "Admin",
        hospital_name=hospital_name,
        role=data.role,
        raw_token=raw_token,
        welcome_message=data.welcome_message,
    )

    return new_user


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{user_id}/role
# ---------------------------------------------------------------------------
@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: str,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Change a user's role."""
    target = db.query(User).filter(
        User.id == user_id,
        User.hospital_id == admin.hospital_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    target.role = data.role
    _write_audit(db, admin.id, "SETTINGS_CHANGE", "user", target.id)
    db.commit()
    db.refresh(target)
    return target


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{user_id}/deactivate
# ---------------------------------------------------------------------------
@router.patch("/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Deactivate a user account."""
    target = db.query(User).filter(
        User.id == user_id,
        User.hospital_id == admin.hospital_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    target.is_active = False
    target.status = "deactivated"
    _write_audit(db, admin.id, "SETTINGS_CHANGE", "user", target.id)
    db.commit()
    db.refresh(target)
    return target


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{user_id}/activate
# ---------------------------------------------------------------------------
@router.patch("/users/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Re-enable a deactivated user account."""
    target = db.query(User).filter(
        User.id == user_id,
        User.hospital_id == admin.hospital_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = True
    target.status = "active"
    _write_audit(db, admin.id, "SETTINGS_CHANGE", "user", target.id)
    db.commit()
    db.refresh(target)
    return target


# ---------------------------------------------------------------------------
# POST /api/admin/users/{user_id}/reinvite
# ---------------------------------------------------------------------------
@router.post("/users/{user_id}/reinvite", response_model=UserResponse)
def reinvite_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Regenerate invite token and resend invitation email."""
    target = db.query(User).filter(
        User.id == user_id,
        User.hospital_id == admin.hospital_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.status == "active":
        raise HTTPException(status_code=400, detail="User already active — cannot reinvite")

    # Regenerate token
    raw_token = _generate_invite_token()
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_TOKEN_EXPIRE_HOURS)

    target.invite_token_hash = token_hash
    target.invite_expires_at = expires_at
    target.status = "invited"
    target.is_active = True

    _write_audit(db, admin.id, "USER_INVITE", "user", target.id)
    db.commit()
    db.refresh(target)

    hospital_name = admin.hospital.name if admin.hospital else "Your Hospital"
    send_invite_email(
        to_email=target.email,
        to_name=target.full_name or target.email.split("@")[0],
        inviter_name=admin.full_name or "Admin",
        hospital_name=hospital_name,
        role=target.role,
        raw_token=raw_token,
    )

    return target


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{user_id}/toggle  (legacy — kept for compat)
# ---------------------------------------------------------------------------
@router.patch("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Legacy: Enable/disable a user account (toggle)."""
    target = db.query(User).filter(
        User.id == user_id,
        User.hospital_id == admin.hospital_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    target.is_active = not target.is_active
    target.status = "active" if target.is_active else "deactivated"
    db.commit()
    return {"id": target.id, "is_active": target.is_active}


# ---------------------------------------------------------------------------
# POST /api/admin/users/invite  (legacy alias — kept for compat)
# ---------------------------------------------------------------------------
@router.post("/users/invite", response_model=UserResponse)
def invite_user_legacy(
    data: UserInvite,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Legacy invite endpoint — delegates to create_user."""
    return create_user(data, db, admin)
