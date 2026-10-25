"""Shared request dependencies for authenticated API routes."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import (
    AuthenticationConfigurationError,
    InvalidAccessToken,
    decode_access_token,
)

bearer_scheme = HTTPBearer(auto_error=False, bearerFormat="JWT")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db_session)],
) -> User:
    """Resolve a token subject to an active database user on every request."""
    unauthorized = HTTPException(
        status_code=401,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except AuthenticationConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is not configured.",
        ) from exc
    except (InvalidAccessToken, ValueError, KeyError, TypeError) as exc:
        raise unauthorized from exc

    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise unauthorized
    return user
