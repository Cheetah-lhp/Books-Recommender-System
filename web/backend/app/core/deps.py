from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Optional[User]:
    if not creds or not creds.credentials:
        return None
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        return None
    return db.get(User, payload["sub"])
