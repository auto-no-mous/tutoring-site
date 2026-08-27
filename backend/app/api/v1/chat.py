import datetime as dt
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import ChatThreadType, UserRole
from app.models.group import Group
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.chat import ChatMessageOut, ChatThreadOut
from app.schemas.tutor import TutorStudentOut
from app.services import chat_service, file_service, tutor_service
from app.services.booking_service import get_student_names
from app.utils.time import ensure_aware

router = APIRouter(prefix="/chat", tags=["chat"])


def _require_tutor(user: CurrentUser) -> None:
    if user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")


def _require_student(user: CurrentUser) -> None:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")


async def _display_title(db: DbSession, thread, current_user: User) -> str:
    if thread.type == ChatThreadType.GROUP.value:
        # group_id is None once the group has been deleted - the thread stays as an
        # archive and falls back to the name snapshotted at that moment
        # (chat_service.archive_group_thread).
        group = await db.get(Group, thread.group_id) if thread.group_id else None
        if group is not None:
            return group.name
        return f"{thread.archived_group_name} (группа удалена)" if thread.archived_group_name else ""
    if current_user.role == UserRole.TUTOR:
        student = await db.get(User, thread.student_id)
        return student.display_name if student else ""
    profile = await db.get(TutorProfile, thread.tutor_id)
    if profile is None:
        return ""
    tutor_user = await db.get(User, profile.user_id)
    return tutor_user.display_name if tutor_user else ""


def _preview(message) -> str:
    if message.content:
        return message.content
    return "📎 Файл"


@router.get("/threads", response_model=list[ChatThreadOut])
async def list_threads(current_user: CurrentUser, db: DbSession) -> list[ChatThreadOut]:
    if current_user.role == UserRole.TUTOR:
        profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
        threads = await chat_service.list_threads_for_tutor(db, profile.id)
    elif current_user.role == UserRole.STUDENT:
        threads = await chat_service.list_threads_for_student(db, current_user.id)
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Недоступно для этой роли")

    thread_ids = [t.id for t in threads]
    # Sequential, not asyncio.gather: AsyncSession isn't safe for concurrent queries.
    unread_counts = await chat_service.get_unread_counts(db, thread_ids, current_user.id)
    last_messages = await chat_service.get_last_messages(db, thread_ids)

    out = []
    for thread in threads:
        title = await _display_title(db, thread, current_user)
        last_message = last_messages.get(thread.id)
        out.append(
            ChatThreadOut.model_validate(thread, from_attributes=True).model_copy(
                update={
                    "display_title": title,
                    "unread_count": unread_counts.get(thread.id, 0),
                    "last_message_preview": _preview(last_message) if last_message else None,
                    # model_copy() doesn't re-run field validators (unlike model_validate()),
                    # so the UTCDateTime field's AfterValidator(to_utc) never fires here - a
                    # raw SQLite-read datetime comes back naive (see utils/time.ensure_aware)
                    # and must be normalized by hand, or the sort below crashes comparing it
                    # against the aware dt.datetime.min fallback for threads with no messages.
                    "last_message_at": ensure_aware(last_message.created_at) if last_message else None,
                }
            )
        )
    # Most recently active thread first; threads with no messages yet sort last.
    out.sort(key=lambda t: t.last_message_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
    return out


@router.get("/students", response_model=list[TutorStudentOut])
async def list_messageable_students(current_user: CurrentUser, db: DbSession) -> list[TutorStudentOut]:
    """Powers the "Новый чат" recipient picker (ChatPanel.vue) - students booked with
    this tutor who don't already have an individual thread with them."""
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await chat_service.list_messageable_students_for_tutor(db, profile.id)
    return [TutorStudentOut(**row) for row in rows]


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
    # Fetching a thread's messages is treated as reading it - see
    # chat_service.mark_thread_read. The frontend polls this endpoint while a thread
    # is open, which keeps the marker fresh for as long as it stays open.
    await chat_service.mark_thread_read(db, thread_id, current_user.id)
    names = await get_student_names(db, [r.sender_id for r in rows])
    return [
        ChatMessageOut.model_validate(r, from_attributes=True).model_copy(
            update={"sender_display_name": names.get(r.sender_id, "")}
        )
        for r in rows
    ]


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
        file_path = await file_service.save_upload(file, "chat", file_service.ALLOWED_ATTACHMENT_TYPES)

    message = await chat_service.send_message(db, thread, current_user, content, file_path)
    return ChatMessageOut.model_validate(message, from_attributes=True).model_copy(
        update={"sender_display_name": current_user.display_name}
    )
