import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.admin import AdminStudentUpdate, AdminTutorUpdate
from app.services import auth_service
from app.utils.names import compose_display_name


async def list_tutors(db: AsyncSession) -> list[TutorProfile]:
    result = await db.execute(select(TutorProfile))
    return list(result.scalars().all())


async def get_tutor_or_404(db: AsyncSession, tutor_id: uuid.UUID) -> TutorProfile:
    profile = await db.get(TutorProfile, tutor_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Репетитор не найден")
    return profile


async def update_tutor(db: AsyncSession, profile: TutorProfile, payload: AdminTutorUpdate) -> TutorProfile:
    data = payload.model_dump(exclude_unset=True)
    first_name = data.pop("first_name", None)
    last_name = data.pop("last_name", None)
    patronymic_provided = "patronymic" in data
    patronymic = data.pop("patronymic", None)
    is_active = data.pop("is_active", None)
    email = data.pop("email", None)

    for field, value in data.items():
        setattr(profile, field, value)

    name_changed = first_name is not None or last_name is not None or patronymic_provided
    email_changed = False
    if name_changed or is_active is not None or email is not None:
        user = await db.get(User, profile.user_id)
        if user is not None:
            if name_changed:
                user.first_name = first_name if first_name is not None else user.first_name
                user.last_name = last_name if last_name is not None else user.last_name
                user.patronymic = patronymic if patronymic_provided else user.patronymic
                user.display_name = compose_display_name(user.first_name, user.last_name, user.patronymic)
            if is_active is not None:
                user.is_active = is_active
            if email is not None:
                email_changed = await auth_service.prepare_email_change(db, user, email)

    await db.commit()
    await db.refresh(profile)

    if email_changed:
        user = await db.get(User, profile.user_id)
        if user is not None:
            await auth_service.send_email_verification(user)

    return profile


async def delete_tutor(db: AsyncSession, profile: TutorProfile) -> None:
    user = await db.get(User, profile.user_id)
    if user is not None:
        await db.delete(user)
    else:
        await db.delete(profile)
    await db.commit()


async def list_students(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).where(User.role == UserRole.STUDENT.value))
    return list(result.scalars().all())


async def get_student_or_404(db: AsyncSession, student_id: uuid.UUID) -> User:
    user = await db.get(User, student_id)
    if user is None or user.role != UserRole.STUDENT.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не найден")
    return user


async def update_student(db: AsyncSession, user: User, payload: AdminStudentUpdate) -> User:
    data = payload.model_dump(exclude_unset=True)

    email_changed = False
    if "email" in data:
        email_changed = await auth_service.prepare_email_change(db, user, data.pop("email"))

    for field, value in data.items():
        setattr(user, field, value)
    if {"first_name", "last_name", "patronymic"} & data.keys():
        user.display_name = compose_display_name(user.first_name, user.last_name, user.patronymic)

    await db.commit()
    await db.refresh(user)

    if email_changed:
        await auth_service.send_email_verification(user)

    return user


async def delete_student(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.commit()
