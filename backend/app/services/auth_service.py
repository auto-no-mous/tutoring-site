import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    JWTError,
    TokenType,
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.tutor import TutorProfile
from app.models.user import RefreshToken, User
from app.schemas.auth import LoginRequest, PasswordResetConfirm, RegisterRequest, TokenPair, VKAuthRequest
from app.schemas.user import UserSettingsUpdate
from app.services.email_service import send_password_reset_email, send_verification_email
from app.utils.names import compose_display_name
from app.utils.time import ensure_aware, utcnow


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _get_user_by_vk_id(db: AsyncSession, vk_id: str) -> User | None:
    result = await db.execute(select(User).where(User.vk_id == vk_id))
    return result.scalar_one_or_none()


async def login_or_register_vk_user(db: AsyncSession, vk_id: str, payload: VKAuthRequest) -> User:
    user = await _get_user_by_vk_id(db, vk_id)
    if user is not None:
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован")
        return user

    # First time we see this VK account: it must be registered with role + consent,
    # same as email registration (section 7). We deliberately don't auto-link by
    # email even if VK happened to return one (section 10).
    if payload.role is None or not payload.first_name or not payload.last_name or not payload.pd_consent:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Для первого входа через VK укажите роль, имя, фамилию и согласие на обработку персональных данных",
        )

    user = User(
        role=payload.role,
        vk_id=vk_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        patronymic=payload.patronymic,
        display_name=compose_display_name(payload.first_name, payload.last_name, payload.patronymic),
        email_verified=False,
        pd_consent_given=True,
        pd_consent_at=utcnow(),
    )
    db.add(user)
    await db.flush()

    if payload.role == UserRole.TUTOR:
        db.add(TutorProfile(user_id=user.id))

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID | str) -> User | None:
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return None
    return await db.get(User, user_uuid)


async def update_user_settings(db: AsyncSession, user: User, payload: UserSettingsUpdate) -> User:
    data = payload.model_dump(exclude_unset=True)

    # Changing email re-requires verification, same as at registration - it's the
    # login identifier, so we don't trust it unproven after a change.
    email_changed = False
    if "email" in data:
        new_email = data.pop("email")
        if new_email != user.email:
            existing = await _get_user_by_email(db, new_email)
            if existing is not None and existing.id != user.id:
                raise HTTPException(status.HTTP_409_CONFLICT, "Эта почта уже используется другим аккаунтом")
            user.email = new_email
            user.email_verified = False
            email_changed = True

    for field, value in data.items():
        setattr(user, field, value)
    if {"first_name", "last_name", "patronymic"} & data.keys():
        user.display_name = compose_display_name(user.first_name, user.last_name, user.patronymic)

    await db.commit()
    await db.refresh(user)

    if email_changed and user.email:
        token = create_email_verification_token(str(user.id))
        await send_verification_email(user.email, token)

    return user


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    existing = await _get_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь с такой почтой уже существует")

    user = User(
        role=payload.role,
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        patronymic=payload.patronymic,
        display_name=compose_display_name(payload.first_name, payload.last_name, payload.patronymic),
        email_verified=False,
        pd_consent_given=True,
        pd_consent_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    if payload.role == UserRole.TUTOR:
        db.add(TutorProfile(user_id=user.id))

    await db.commit()
    await db.refresh(user)

    token = create_email_verification_token(str(user.id))
    await send_verification_email(user.email, token)

    return user


async def authenticate_user(db: AsyncSession, payload: LoginRequest) -> User:
    user = await _get_user_by_email(db, payload.email)
    if user is None or user.password_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверная почта или пароль")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверная почта или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован")
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> TokenPair:
    access_token = create_access_token(str(user.id), user.role)
    refresh_token, jti, expires_at = create_refresh_token(str(user.id))
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    await db.commit()
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


async def refresh_token_pair(db: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалидный refresh-токен")

    if payload.get("type") != TokenType.REFRESH.value:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалидный refresh-токен")

    jti = payload.get("jti")
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    stored = result.scalar_one_or_none()
    if stored is None or stored.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh-токен отозван")
    if ensure_aware(stored.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh-токен истёк")

    user = await get_user_by_id(db, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")

    # Rotate: revoke the used refresh token, issue a fresh pair.
    stored.revoked = True
    await db.commit()

    return await issue_token_pair(db, user)


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        return
    jti = payload.get("jti")
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    stored = result.scalar_one_or_none()
    if stored is not None:
        stored.revoked = True
        await db.commit()


async def verify_email(db: AsyncSession, token: str) -> User:
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невалидная или истёкшая ссылка")
    if payload.get("type") != TokenType.EMAIL_VERIFY.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невалидная ссылка подтверждения")

    user = await get_user_by_id(db, payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    user.email_verified = True
    await db.commit()
    await db.refresh(user)
    return user


async def request_password_reset(db: AsyncSession, email: str) -> None:
    user = await _get_user_by_email(db, email)
    # Do not reveal whether the email is registered.
    if user is None or user.password_hash is None:
        return
    token = create_password_reset_token(str(user.id))
    await send_password_reset_email(user.email, token)


async def confirm_password_reset(db: AsyncSession, payload: PasswordResetConfirm) -> None:
    try:
        decoded = decode_token(payload.token)
    except JWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невалидная или истёкшая ссылка")
    if decoded.get("type") != TokenType.PASSWORD_RESET.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Невалидная ссылка сброса пароля")

    user = await get_user_by_id(db, decoded["sub"])
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    user.password_hash = hash_password(payload.new_password)
    await db.commit()
