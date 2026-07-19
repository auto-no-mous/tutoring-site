import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import ChatThreadType, UserRole
from app.models.group import Group
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.chat import ChatMessageOut, ChatThreadOut
from app.services import chat_service, file_service, tutor_service

router = APIRouter(prefix="/chat", tags=["chat"])


def _require_tutor(user: CurrentUser) -> None:
    if user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")


def _require_student(user: CurrentUser) -> None:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")


async def _display_title(db: DbSession, thread, current_user: User) -> str:
    if thread.type == ChatThreadType.GROUP.value:
        group = await db.get(Group, thread.group_id)
        return group.name if group else ""
    if current_user.role == UserRole.TUTOR:
        student = await db.get(User, thread.student_id)
        return student.display_name if student else ""
    profile = await db.get(TutorProfile, thread.tutor_id)
    if profile is None:
        return ""
    tutor_user = await db.get(User, profile.user_id)
    return tutor_user.display_name if tutor_user else ""


@router.get("/threads", response_model=list[ChatThreadOut])
async def list_threads(current_user: CurrentUser, db: DbSession) -> list[ChatThreadOut]:
    if current_user.role == UserRole.TUTOR:
        profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
        threads = await chat_service.list_threads_for_tutor(db, profile.id)
    elif current_user.role == UserRole.STUDENT:
        threads = await chat_service.list_threads_for_student(db, current_user.id)
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Недоступно для этой роли")

    out = []
    for thread in threads:
        title = await _display_title(db, thread, current_user)
        out.append(ChatThreadOut.model_validate(thread, from_attributes=True).model_copy(update={"display_title": title}))
    return out


@router.post("/threads/with-student/{student_id}", response_model=ChatThreadOut)
async def open_thread_with_student(student_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ChatThreadOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    student = await db.get(User, student_id)
    if student is None or student.role != UserRole.STUDENT.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не найден")
    thread = await chat_service.get_or_create_individual_thread(db, profile.id, student_id)
    title = await _display_title(db, thread, current_user)
    return ChatThreadOut.model_validate(thread, from_attributes=True).model_copy(update={"display_title": title})


@router.post("/threads/with-tutor/{tutor_id}", response_model=ChatThreadOut)
async def open_thread_with_tutor(tutor_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ChatThreadOut:
    _require_student(current_user)
    await tutor_service.get_profile_by_id(db, tutor_id)
    thread = await chat_service.get_or_create_individual_thread(db, tutor_id, current_user.id)
    title = await _display_title(db, thread, current_user)
    return ChatThreadOut.model_validate(thread, from_attributes=True).model_copy(update={"display_title": title})


@router.get("/threads/group/{group_id}", response_model=ChatThreadOut)
async def get_group_thread(group_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ChatThreadOut:
    thread = await chat_service.get_group_thread_or_404(db, group_id)
    if not await chat_service.can_access_thread(db, thread, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к этому чату")
    title = await _display_title(db, thread, current_user)
    return ChatThreadOut.model_validate(thread, from_attributes=True).model_copy(update={"display_title": title})


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(thread_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> list[ChatMessageOut]:
    thread = await chat_service.get_thread_or_404(db, thread_id)
    if not await chat_service.can_access_thread(db, thread, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к этому чату")
    rows = await chat_service.list_messages(db, thread_id)
    return [ChatMessageOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/threads/{thread_id}/messages", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    thread_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> ChatMessageOut:
    thread = await chat_service.get_thread_or_404(db, thread_id)
    if not await chat_service.can_access_thread(db, thread, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к этому чату")

    file_path = None
    if file is not None and file.filename:
        file_path = await file_service.save_upload(file, "chat")

    message = await chat_service.send_message(db, thread, current_user, content, file_path)
    return ChatMessageOut.model_validate(message, from_attributes=True)
