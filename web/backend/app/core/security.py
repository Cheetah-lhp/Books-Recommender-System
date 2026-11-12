from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def _encode(payload: dict[str, Any], expires_delta: timedelta) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + expires_delta
    data["iat"] = datetime.now(timezone.utc)
    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, email: str) -> str:
    return _encode(
        {"sub": user_id, "email": email, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> tuple[str, str]:
    jti = str(uuid4())
    token = _encode(
        {"sub": user_id, "type": "refresh", "jti": jti},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token, jti


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
