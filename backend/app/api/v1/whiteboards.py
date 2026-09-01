import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import UserRole
from app.schemas.whiteboard import WhiteboardCreate, WhiteboardOut, WhiteboardUpdate
from app.services import tutor_service, whiteboard_service

router = APIRouter(prefix="/whiteboards", tags=["whiteboards"])


def _require_tutor(user: CurrentUser) -> None:
    if user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")


@router.get("/my", response_model=list[WhiteboardOut])
async def list_my_whiteboards(current_user: CurrentUser, db: DbSession) -> list[WhiteboardOut]:
    """Все доски, видимые пользователю, сразу списком.

    Карточки занятий разбирают его по student_id/group_id сами: доска относится к
    паре или к группе, а не к записи в расписании, и запрашивать её на каждую
    карточку значило бы повторять один и тот же ответ десятки раз.
    """
    boards = await whiteboard_service.list_for_user(db, current_user)
    return [WhiteboardOut.model_validate(board) for board in boards]


@router.post("", response_model=WhiteboardOut, status_code=status.HTTP_201_CREATED)
async def create_whiteboard(
    payload: WhiteboardCreate, current_user: CurrentUser, db: DbSession
) -> WhiteboardOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    board = await whiteboard_service.create(db, profile, payload)
    return WhiteboardOut.model_validate(board)


@router.patch("/{board_id}", response_model=WhiteboardOut)
async def update_whiteboard(
    board_id: uuid.UUID, payload: WhiteboardUpdate, current_user: CurrentUser, db: DbSession
) -> WhiteboardOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    board = await whiteboard_service.update(db, profile, board_id, payload)
    return WhiteboardOut.model_validate(board)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_whiteboard(board_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    await whiteboard_service.delete(db, profile, board_id)


@router.post("/{board_id}/use", response_model=WhiteboardOut)
async def mark_whiteboard_used(
    board_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> WhiteboardOut:
    """Отметить доску открытой - она поднимется наверх списка у обеих сторон."""
    board = await whiteboard_service.mark_used(db, current_user, board_id)
    return WhiteboardOut.model_validate(board)
