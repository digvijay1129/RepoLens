"""Email/password account endpoints for the local RepoLens workspace."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import (
    AuthenticationConfigurationError,
    create_access_token,
    ensure_authentication_configured,
    hash_password,
    verify_password,
)

router = APIRouter()


def _require_auth_configuration() -> None:
    try:
        ensure_authentication_configured()
    except AuthenticationConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is not configured. Set JWT_SECRET_KEY in backend/.env.",
        ) from exc


def _issue_token(user: User) -> AccessTokenResponse:
    try:
        token, expires_in = create_access_token(user.id, user.email)
    except AuthenticationConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is not configured. Set JWT_SECRET_KEY in backend/.env.",
        ) from exc
    return AccessTokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=AccessTokenResponse, status_code=201)
def register(
    body: RegisterRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> AccessTokenResponse:
    """Register a new workspace account and return a bearer token."""
    _require_auth_configuration()
    existing = db.scalar(select(User.id).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        ) from exc
    return _issue_token(user)


@router.post("/login", response_model=AccessTokenResponse)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> AccessTokenResponse:
    """Authenticate an account without disclosing whether its email exists."""
    _require_auth_configuration()
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _issue_token(user)


@router.get("/me", response_model=UserResponse)
def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the authenticated user's public account profile."""
    return UserResponse.model_validate(current_user)
