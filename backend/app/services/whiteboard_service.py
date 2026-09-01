"""Онлайн-доски: список ссылок, который репетитор ведёт с учеником или с группой.

Доска привязана к паре репетитор-ученик (или к группе), а не к конкретному занятию:
с одним учеником месяцами работают на одной и той же доске, и вбивать ссылку заново
к каждой записи в расписании было бы мучением. Карточка занятия показывает ту доску,
которую открывали последней, остальные прячет под кнопку - см. last_used_at.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GroupMembershipStatus, UserRole
from app.models.group import Group, GroupMembership
from app.models.tutor import TutorProfile
from app.models.user import User
from app.models.whiteboard import Whiteboard
from app.schemas.whiteboard import WhiteboardCreate, WhiteboardUpdate
from app.utils.time import utcnow

# Досок у пары обычно одна, изредка несколько по темам. Предел нужен не от жадности,
# а чтобы список в карточке занятия оставался списком, а не свалкой.
MAX_WHITEBOARDS_PER_OWNER = 20


async def _owned_group(db: AsyncSession, tutor: TutorProfile, group_id: uuid.UUID) -> Group:
    group = await db.get(Group, group_id)
    if group is None or group.tutor_id != tutor.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Группа не найдена")
    return group


async def create(db: AsyncSession, tutor: TutorProfile, payload: WhiteboardCreate) -> Whiteboard:
    if payload.group_id is not None:
        await _owned_group(db, tutor, payload.group_id)
    else:
        student = await db.get(User, payload.student_id)
        if student is None or student.role != UserRole.STUDENT.value:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не найден")

    owner_filter = (
        Whiteboard.group_id == payload.group_id
        if payload.group_id is not None
        else Whiteboard.student_id == payload.student_id
    )
    existing = await db.execute(
        select(Whiteboard).where(Whiteboard.tutor_id == tutor.id, owner_filter)
    )
    if len(existing.scalars().all()) >= MAX_WHITEBOARDS_PER_OWNER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Больше {MAX_WHITEBOARDS_PER_OWNER} досок на одного ученика или группу не бывает",
        )

    board = Whiteboard(
        tutor_id=tutor.id,
        student_id=payload.student_id,
        group_id=payload.group_id,
        url=str(payload.url),
        title=payload.title,
        last_used_at=utcnow(),
    )
    db.add(board)
    await db.commit()
    await db.refresh(board)
    return board


async def get_own_or_404(db: AsyncSession, tutor: TutorProfile, board_id: uuid.UUID) -> Whiteboard:
    board = await db.get(Whiteboard, board_id)
    if board is None or board.tutor_id != tutor.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Доска не найдена")
    return board


async def update(
    db: AsyncSession, tutor: TutorProfile, board_id: uuid.UUID, payload: WhiteboardUpdate
) -> Whiteboard:
    board = await get_own_or_404(db, tutor, board_id)
    data = payload.model_dump(exclude_unset=True)
    if "url" in data and data["url"] is not None:
        board.url = str(data["url"])
    if "title" in data:
        board.title = data["title"]
    await db.commit()
    await db.refresh(board)
    return board


async def delete(db: AsyncSession, tutor: TutorProfile, board_id: uuid.UUID) -> None:
    board = await get_own_or_404(db, tutor, board_id)
    await db.delete(board)
    await db.commit()


async def list_for_user(db: AsyncSession, user: User) -> list[Whiteboard]:
    """Все доски, которые пользователю положено видеть.

    Репетитору - свои; ученику - доски его пар с репетиторами и доски групп, в
    которых он состоит. Одним запросом на всю вкладку: доска относится к паре, а не к
    занятию, поэтому карточки разбирают общий список по student_id/group_id, а не
    ходят на сервер за каждой записью в расписании.
    """
    if user.role == UserRole.TUTOR.value:
        profile = await db.execute(select(TutorProfile).where(TutorProfile.user_id == user.id))
        tutor = profile.scalar_one_or_none()
        if tutor is None:
            return []
        query = select(Whiteboard).where(Whiteboard.tutor_id == tutor.id)
    else:
        member_groups = select(GroupMembership.group_id).where(
            GroupMembership.student_id == user.id,
            GroupMembership.status == GroupMembershipStatus.ACTIVE.value,
        )
        query = select(Whiteboard).where(
            or_(
                Whiteboard.student_id == user.id,
                Whiteboard.group_id.in_(member_groups),
            )
        )

    result = await db.execute(query.order_by(Whiteboard.last_used_at.desc()))
    return list(result.scalars().all())


async def mark_used(db: AsyncSession, user: User, board_id: uuid.UUID) -> Whiteboard:
    """Отмечает доску открытой - она поднимается наверх списка.

    Право отметить есть у обеих сторон занятия: «последняя открытая» описывает их
    общую работу, а не выбор одного репетитора. Проверка доступа - через тот же
    список, что рисует карточки, чтобы правила не разъезжались.
    """
    visible = {board.id: board for board in await list_for_user(db, user)}
    board = visible.get(board_id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Доска не найдена")

    board.last_used_at = utcnow()
    await db.commit()
    await db.refresh(board)
    return board
