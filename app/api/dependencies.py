"""Shared FastAPI dependencies only; domain dependencies stay in their modules."""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    user_public_id: Annotated[uuid.UUID | None, Header(alias="X-User-Public-ID")] = None,
) -> User:
    """Resolve an explicit development user without weakening production authentication."""
    if settings.app_env not in {"local", "test"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Host authentication integration is required",
        )
    if user_public_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Development user is required")
    user = db.scalar(select(User).where(User.public_id == user_public_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Development user was not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
