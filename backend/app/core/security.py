import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"
    # Промежуточный токен между колбэком VK/Яндекса и созданием аккаунта: провайдер
    # подтвердил, кто пользователь, но роль и согласие на обработку ПД он ещё не
    # выбрал - см. app.services.oauth_service.
    OAUTH_SIGNUP = "oauth_signup"


# bcrypt hard-caps input at 72 bytes; anything past that is truncated (matches common
# framework behavior, e.g. Django). Not using passlib: it's unmaintained and breaks
# under modern bcrypt releases (bcrypt>=4.1 removed the __about__ attribute passlib's
# version sniffing relies on).
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims={"role": role},
    )


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at) so the caller can persist jti for revocation."""
    jti = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": TokenType.REFRESH.value,
        "iat": now,
        "exp": expires_at,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def create_email_verification_token(user_id: str) -> str:
    return _create_token(user_id, TokenType.EMAIL_VERIFY, timedelta(hours=48))


def create_password_reset_token(user_id: str) -> str:
    return _create_token(user_id, TokenType.PASSWORD_RESET, timedelta(hours=2))


# Токен живёт ровно столько, сколько человек заполняет форму "роль + согласие" после
# возврата из VK/Яндекса, и не даёт доступа ни к чему, кроме создания аккаунта с уже
# подтверждённой провайдером идентичностью.
OAUTH_SIGNUP_TOKEN_TTL = timedelta(minutes=15)


def create_oauth_signup_token(
    provider: str,
    provider_user_id: str,
    email: str | None,
    first_name: str | None = None,
    last_name: str | None = None,
    avatar_url: str | None = None,
) -> str:
    """Данные профиля едут внутри подписанного токена, а не возвращаются формой:
    имя, почта и аватар взяты у провайдера, и подменить их по дороге через браузер
    не должно быть возможно."""
    return _create_token(
        subject=provider_user_id,
        token_type=TokenType.OAUTH_SIGNUP,
        expires_delta=OAUTH_SIGNUP_TOKEN_TTL,
        extra_claims={
            "provider": provider,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "avatar_url": avatar_url,
        },
    )


def decode_token(token: str) -> dict[str, Any]:
    """Raises jose.JWTError on invalid/expired token."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


__all__ = [
    "JWTError",
    "TokenType",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "create_email_verification_token",
    "create_password_reset_token",
    "create_oauth_signup_token",
    "decode_token",
]
