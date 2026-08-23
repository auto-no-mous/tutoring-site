import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.subject import Direction, Subject, TutorSubject, TutorSubjectDirection
from app.models.tutor import TutorProfile
from app.schemas.subject import DirectionOut, SubjectCreate, SubjectUpdate, TutorSubjectOut, TutorSubjectSelection

# --- Admin-managed subject/direction catalog ------------------------------------


async def list_subjects(db: AsyncSession) -> list[Subject]:
    result = await db.execute(select(Subject).options(selectinload(Subject.directions)).order_by(Subject.name))
    return list(result.scalars().all())


async def get_visible_tutor_counts(db: AsyncSession) -> dict[uuid.UUID, int]:
    """How many catalog-visible tutors teach each subject, keyed by subject id.

    Repeats search_catalog's is_hidden filter on purpose: the home page uses these
    counts to decide which subject tiles to show, so a tile must never lead to an
    empty catalog."""
    result = await db.execute(
        select(TutorSubject.subject_id, func.count(func.distinct(TutorSubject.tutor_id)))
        .join(TutorProfile, TutorProfile.id == TutorSubject.tutor_id)
        .where(TutorProfile.is_hidden.is_(False))
        .group_by(TutorSubject.subject_id)
    )
    return {subject_id: count for subject_id, count in result.all()}


async def get_subject_or_404(db: AsyncSession, subject_id: uuid.UUID) -> Subject:
    result = await db.execute(
        select(Subject).options(selectinload(Subject.directions)).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Предмет не найден")
    return subject


async def create_subject(db: AsyncSession, payload: SubjectCreate) -> Subject:
    existing = await db.execute(select(Subject).where(Subject.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой предмет уже существует")
    subject = Subject(name=payload.name)
    db.add(subject)
    await db.commit()
    return await get_subject_or_404(db, subject.id)


async def update_subject(db: AsyncSession, subject: Subject, payload: SubjectUpdate) -> Subject:
    subject.name = payload.name
    await db.commit()
    return await get_subject_or_404(db, subject.id)


async def delete_subject(db: AsyncSession, subject: Subject) -> None:
    await db.delete(subject)
    await db.commit()


async def create_direction(db: AsyncSession, subject: Subject, name: str) -> Direction:
    existing = await db.execute(
        select(Direction).where(Direction.subject_id == subject.id, Direction.name == name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такое направление уже есть у этого предмета")
    direction = Direction(subject_id=subject.id, name=name)
    db.add(direction)
    await db.commit()
    await db.refresh(direction)
    return direction


async def get_direction_or_404(db: AsyncSession, direction_id: uuid.UUID) -> Direction:
    direction = await db.get(Direction, direction_id)
    if direction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Направление не найдено")
    return direction


async def update_direction(db: AsyncSession, direction: Direction, name: str) -> Direction:
    existing = await db.execute(
        select(Direction).where(
            Direction.subject_id == direction.subject_id, Direction.name == name, Direction.id != direction.id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такое направление уже есть у этого предмета")
    direction.name = name
    await db.commit()
    await db.refresh(direction)
    return direction


async def delete_direction(db: AsyncSession, direction: Direction) -> None:
    await db.delete(direction)
    await db.commit()


# --- Tutor subject/direction selection ------------------------------------------


async def get_tutor_subjects(db: AsyncSession, tutor_id: uuid.UUID) -> list[TutorSubject]:
    result = await db.execute(
        select(TutorSubject)
        .options(
            selectinload(TutorSubject.subject),
            selectinload(TutorSubject.directions).selectinload(TutorSubjectDirection.direction),
        )
        .where(TutorSubject.tutor_id == tutor_id)
    )
    return list(result.scalars().all())


def to_tutor_subject_out(rows: list[TutorSubject]) -> list[TutorSubjectOut]:
    return [
        TutorSubjectOut(
            subject_id=row.subject_id,
            subject_name=row.subject.name,
            directions=[
                DirectionOut(id=tsd.direction.id, subject_id=tsd.direction.subject_id, name=tsd.direction.name)
                for tsd in row.directions
            ],
        )
        for row in rows
    ]


async def replace_tutor_subjects(
    db: AsyncSession, tutor: TutorProfile, selections: list[TutorSubjectSelection]
) -> list[TutorSubject]:
    subject_ids = {s.subject_id for s in selections}
    if subject_ids:
        result = await db.execute(
            select(Subject).options(selectinload(Subject.directions)).where(Subject.id.in_(subject_ids))
        )
        subjects_by_id = {s.id: s for s in result.scalars().all()}
        if len(subjects_by_id) != len(subject_ids):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Один из предметов не найден")
        for selection in selections:
            subject = subjects_by_id[selection.subject_id]
            valid_direction_ids = {d.id for d in subject.directions}
            if not set(selection.direction_ids).issubset(valid_direction_ids):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"Указано направление, не относящееся к предмету «{subject.name}»",
                )

    existing = await db.execute(select(TutorSubject).where(TutorSubject.tutor_id == tutor.id))
    for row in existing.scalars().all():
        await db.delete(row)
    await db.flush()

    for selection in selections:
        tutor_subject = TutorSubject(tutor_id=tutor.id, subject_id=selection.subject_id)
        db.add(tutor_subject)
        await db.flush()
        for direction_id in selection.direction_ids:
            db.add(TutorSubjectDirection(tutor_subject_id=tutor_subject.id, direction_id=direction_id))

    await db.commit()
    return await get_tutor_subjects(db, tutor.id)


async def get_subject_names_for_tutors(db: AsyncSession, tutor_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not tutor_ids:
        return {}
    result = await db.execute(
        select(TutorSubject.tutor_id, Subject.name)
        .join(Subject, Subject.id == TutorSubject.subject_id)
        .where(TutorSubject.tutor_id.in_(tutor_ids))
        .order_by(Subject.name)
    )
    out: dict[uuid.UUID, list[str]] = {}
    for tutor_id, subject_name in result.all():
        out.setdefault(tutor_id, []).append(subject_name)
    return out
