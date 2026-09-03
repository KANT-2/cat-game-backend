"""Shared FastAPI dependencies only; domain dependencies stay in their modules."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user() -> User:
    """Authentication integration point supplied by the host application."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Host authentication integration is required",
    )


DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
