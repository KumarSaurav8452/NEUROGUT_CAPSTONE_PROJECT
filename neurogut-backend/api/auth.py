"""
NEUROGUT -- Authentication API
================================
JWT login, token validation, role-based access middleware.
v4.0: Added accept-invite endpoint for token-based user onboarding.
"""

import os
import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User
from schemas.patient import LoginRequest, TokenResponse, UserResponse, InviteAccept

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET", "neurogut-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return the User ORM object."""
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_role(*roles: str):
    """Dependency factory: restrict access to specific roles."""
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not authorized. Required: {roles}",
            )
        return user
    return role_checker


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password, receive JWT."""
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.password_hash or not _verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": user.id, "role": user.role, "hospital": user.hospital_id})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        full_name=user.full_name,
        hospital_id=user.hospital_id,
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return user


@router.post("/accept-invite", response_model=TokenResponse)
def accept_invite(req: InviteAccept, db: Session = Depends(get_db)):
    """
    Accept an invitation token and set a new password.
    Transitions user status: invited -> active.
    Returns a JWT so the user is immediately logged in.
    """
    # Hash the submitted token to compare with stored hash
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()

    # Find user by token hash
    user = db.query(User).filter(User.invite_token_hash == token_hash).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already-used invitation link",
        )

    # Check expiry
    if user.invite_expires_at:
        expires = user.invite_expires_at
        # Make offset-aware if naive
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation link has expired. Please ask your admin to resend.",
            )

    # Set password and activate user
    user.password_hash = bcrypt.hashpw(
        req.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    user.status = "active"
    user.is_active = True
    user.invite_token_hash = None   # consume token
    user.invite_expires_at = None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Issue JWT
    token = create_access_token({"sub": user.id, "role": user.role, "hospital": user.hospital_id})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        full_name=user.full_name,
        hospital_id=user.hospital_id,
    )
