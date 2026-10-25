"""Password hashing and signed access-token helpers."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pydantic import SecretStr

from app.core.config import get_settings

ALGORITHM = "HS256"
TOKEN_ISSUER = "repolens"
TOKEN_AUDIENCE = "repolens-api"
password_hasher = PasswordHash.recommended()


class AuthenticationConfigurationError(RuntimeError):
    """Raised when authentication secrets are missing or not production-safe."""


class InvalidAccessToken(RuntimeError):
    """Raised when an access token is invalid, expired, or malformed."""


def hash_password(password: str) -> str:
    """Hash a plaintext password using the recommended Argon2id configuration."""
    return password_hasher.hash(password)


def verify_password(password: str, encoded_hash: str | None) -> bool:
    """Verify a password without exposing malformed stored hashes to callers."""
    if not encoded_hash:
        return False
    try:
        return password_hasher.verify(password, encoded_hash)
    except Exception:
        return False


def _get_jwt_secret() -> str:
    value: SecretStr | None = get_settings().jwt_secret_key
    if value is None:
        raise AuthenticationConfigurationError(
            "Authentication is not configured. Set JWT_SECRET_KEY in backend/.env."
        )
    secret = value.get_secret_value()
    if len(secret.encode("utf-8")) < 32:
        raise AuthenticationConfigurationError(
            "JWT_SECRET_KEY must contain at least 32 bytes. Generate a new local secret."
        )
    return secret


def ensure_authentication_configured() -> None:
    """Validate the signing secret before mutating account state."""
    _get_jwt_secret()


def create_access_token(user_id: UUID, email: str) -> tuple[str, int]:
    """Create a short-lived HS256 bearer token with issuer, audience and expiry."""
    settings = get_settings()
    expires_in = settings.jwt_access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "type": "access",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM), expires_in


def decode_access_token(token: str) -> dict:
    """Decode and validate a signed access token."""
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "iss", "aud", "type"]},
        )
    except AuthenticationConfigurationError:
        raise
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken("Access token is invalid or expired.") from exc

    if payload.get("type") != "access":
        raise InvalidAccessToken("Access token is invalid or expired.")
    try:
        UUID(payload["sub"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidAccessToken("Access token is invalid or expired.") from exc
    return payload
