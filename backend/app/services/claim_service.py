"""Передача заведённого репетитором профиля самому ученику.

Репетитор выдаёт ссылку вида /claim/<token>, ученик открывает её и задаёт способ
входа: почту с паролем либо VK/Яндекс. Технически это не перенос данных, а привязка
первого способа входа к уже существующей строке users - поэтому вся история занятий,
групп и домашних заданий остаётся на месте, id не меняется.

С этого момента аккаунт перестаёт быть управляемым: managed_by_tutor_id обнуляется, и
ФИО с классом правит уже сам ученик в настройках.
"""

import logging
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.student import ClaimLinkOut, ClaimPreviewOut, ClaimWithPasswordRequest
from app.services import auth_service
from app.utils.time import ensure_aware, utcnow

logger = logging.getLogger("app.claim")

# Ссылка живёт достаточно долго, чтобы ученик дошёл до неё между занятиями, но не
# вечно: пока она действует, любой, кто её увидел, может занять аккаунт.
CLAIM_TOKEN_TTL = timedelta(days=30)


def _claim_url(token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/claim/{token}"


async def issue_claim_link(db: AsyncSession, student: User) -> ClaimLinkOut:
    """Выдаёт новую ссылку-приглашение, обесценивая прежнюю."""
    student.claim_token = secrets.token_urlsafe(32)
    student.claim_token_expires_at = utcnow() + CLAIM_TOKEN_TTL
    await db.commit()
    await db.refresh(student)
    return ClaimLinkOut(url=_claim_url(student.claim_token), expires_at=student.claim_token_expires_at)


async def get_claimable_user(db: AsyncSession, token: str) -> User:
    """Ученик по токену из ссылки. Токен годится, только пока аккаунт никем не забран."""
    result = await db.execute(select(User).where(User.claim_token == token))
    student = result.scalar_one_or_none()
    if student is None or not student.is_managed:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Ссылка недействительна. Попросите репетитора прислать новую.",
        )
    if student.claim_token_expires_at is None or ensure_aware(student.claim_token_expires_at) < utcnow():
        raise HTTPException(
            status.HTTP_410_GONE,
            "Срок действия ссылки истёк. Попросите репетитора прислать новую.",
        )
    return student


async def preview(db: AsyncSession, token: str) -> ClaimPreviewOut:
    student = await get_claimable_user(db, token)
    tutor_name = "репетитор"
    if student.managed_by_tutor_id is not None:
        profile = await db.get(TutorProfile, student.managed_by_tutor_id)
        if profile is not None:
            tutor_user = await db.get(User, profile.user_id)
            if tutor_user is not None:
                tutor_name = tutor_user.display_name
    return ClaimPreviewOut(
        display_name=student.display_name, grade=student.grade, tutor_display_name=tutor_name
    )


async def finalize(db: AsyncSession, student: User) -> None:
    """Общий хвост обоих способов: аккаунт перестаёт быть управляемым, ссылка гаснет.

    Вызывается и при задании пароля, и после привязки VK/Яндекса (oauth_service).
    """
    student.managed_by_tutor_id = None
    student.claim_token = None
    student.claim_token_expires_at = None
    student.pd_consent_given = True
    student.pd_consent_at = utcnow()
    await db.commit()
    await db.refresh(student)


async def claim_with_password(db: AsyncSession, payload: ClaimWithPasswordRequest) -> User:
    student = await get_claimable_user(db, payload.token)

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        # Слияние двух историй занятий - отдельная задача с риском перепутать чужие
        # данные, поэтому здесь честный отказ, а не тихое связывание.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "На эту почту уже зарегистрирован аккаунт. Войдите в него, а перенос "
            "занятий из профиля у репетитора попросите сделать администратора.",
        )

    student.email = payload.email
    student.password_hash = hash_password(payload.password)
    # Почта не подтверждена: ссылку с подтверждением отправляем сразу после того,
    # как аккаунт станет самостоятельным.
    student.email_verified = False
    await finalize(db, student)

    try:
        await auth_service.send_email_verification(student)
    except Exception:
        logger.exception("CLAIM: не удалось отправить письмо подтверждения user_id=%s", student.id)
    return student
