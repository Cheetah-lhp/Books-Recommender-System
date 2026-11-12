import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import Profile, RefreshToken, User, UserRole
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_tokens(db: Session, user: User, full_name: str = "") -> TokenResponse:
    access = create_access_token(user.id, user.email)
    refresh, _jti = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_token_hash(refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut(id=user.id, email=user.email, full_name=full_name or None),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, full_name=body.full_name or body.email.split("@")[0]))
    db.add(UserRole(user_id=user.id, role="user"))
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user, body.full_name)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    profile = db.get(Profile, user.id)
    return _issue_tokens(db, user, profile.full_name if profile else "")


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    th = _token_hash(body.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == th, RefreshToken.revoked == 0).first()
    if not row or row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    row.revoked = 1
    db.commit()
    profile = db.get(Profile, user.id)
    return _issue_tokens(db, user, profile.full_name if profile else "")


@router.post("/logout")
def logout(body: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    th = _token_hash(body.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == th).first()
    if row:
        row.revoked = 1
        db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    profile = db.get(Profile, user.id)
    return UserOut(id=user.id, email=user.email, full_name=profile.full_name if profile else None)
