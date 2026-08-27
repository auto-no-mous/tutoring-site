import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatThread, ChatThreadRead
from app.models.enums import ChatThreadType, GroupMembershipStatus, NotificationEvent
from app.models.group import GroupMembership
from app.models.user import User
from app.services import notification_service, tutor_service
from app.services.booking_service import list_students_for_tutor
from app.utils.time import utcnow


async def get_or_create_individual_thread(db: AsyncSession, tutor_id: uuid.UUID, student_id: uuid.UUID) -> ChatThread:
    result = await db.execute(
        select(ChatThread).where(
            ChatThread.type == ChatThreadType.INDIVIDUAL.value,
            ChatThread.tutor_id == tutor_id,
            ChatThread.student_id == student_id,
        )
    )
    thread = result.scalar_one_or_none()
    if thread is not None:
        return thread

    thread = ChatThread(type=ChatThreadType.INDIVIDUAL.value, tutor_id=tutor_id, student_id=student_id)
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return thread


async def create_group_thread(db: AsyncSession, tutor_id: uuid.UUID, group_id: uuid.UUID) -> ChatThread:
    thread = ChatThread(type=ChatThreadType.GROUP.value, tutor_id=tutor_id, group_id=group_id)
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return thread


async def archive_group_thread(db: AsyncSession, group_id: uuid.UUID, group_name: str) -> ChatThread | None:
    """Detaches a group's chat from the group that is about to be deleted, keeping the
    messages themselves (section 2.11 - the correspondence is not what's being deleted).
    The name is copied over because the group row won't be there to supply it anymore.

    Doesn't commit: the caller deletes the group in the same transaction, so the thread
    must not be left detached if that delete fails.
    """
    result = await db.execute(
        select(ChatThread).where(ChatThread.type == ChatThreadType.GROUP.value, ChatThread.group_id == group_id)
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        return None
    thread.archived_group_name = group_name
    thread.group_id = None
    await db.flush()
    return thread


async def get_thread_or_404(db: AsyncSession, thread_id: uuid.UUID) -> ChatThread:
    thread = await db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Чат не найден")
    return thread


async def get_group_thread_or_404(db: AsyncSession, group_id: uuid.UUID) -> ChatThread:
    result = await db.execute(
        select(ChatThread).where(ChatThread.type == ChatThreadType.GROUP.value, ChatThread.group_id == group_id)
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Чат группы не найден")
    return thread


async def _is_active_member(db: AsyncSession, group_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.student_id == student_id,
            GroupMembership.status == GroupMembershipStatus.ACTIVE.value,
        )
    )
    return result.scalar_one_or_none() is not None


async def can_access_thread(db: AsyncSession, thread: ChatThread, user: User) -> bool:
    if user.role == "tutor":
        profile = await tutor_service.get_profile_by_user_id(db, user.id)
        return thread.tutor_id == profile.id
    if user.role == "student":
        if thread.type == ChatThreadType.INDIVIDUAL.value:
            return thread.student_id == user.id
        # group_id is None on a thread whose group was deleted (archive_group_thread).
        # Deletion requires an empty group, so no student loses access they still had;
        # from here on the archive is the tutor's alone.
        if thread.group_id is None:
            return False
        return await _is_active_member(db, thread.group_id, user.id)
    return False


async def list_threads_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[ChatThread]:
    result = await db.execute(select(ChatThread).where(ChatThread.tutor_id == tutor_id))
    return list(result.scalars().all())


async def list_threads_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[ChatThread]:
    individual = await db.execute(
        select(ChatThread).where(
            ChatThread.type == ChatThreadType.INDIVIDUAL.value, ChatThread.student_id == student_id
        )
    )
    memberships = await db.execute(
        select(GroupMembership.group_id).where(
            GroupMembership.student_id == student_id, GroupMembership.status == GroupMembershipStatus.ACTIVE.value
        )
    )
    group_ids = [row[0] for row in memberships.all()]
    threads = list(individual.scalars().all())
    if group_ids:
        group_threads = await db.execute(
            select(ChatThread).where(
                ChatThread.type == ChatThreadType.GROUP.value, ChatThread.group_id.in_(group_ids)
            )
        )
        threads += list(group_threads.scalars().all())
    return threads


async def list_messageable_students_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[dict]:
    """Students the tutor could start a genuinely NEW individual chat with - booked
    with them, but with no individual thread yet. Once a thread exists, that student
    belongs in the ordinary thread list (ChatPanel.vue), not this "Новый чат" picker -
    otherwise picking them here would look like starting fresh but actually reopen an
    existing conversation."""
    booked = await list_students_for_tutor(db, tutor_id)

    thread_result = await db.execute(
        select(ChatThread.student_id).where(
            ChatThread.tutor_id == tutor_id, ChatThread.type == ChatThreadType.INDIVIDUAL.value
        )
    )
    already_threaded_ids = {row[0] for row in thread_result.all()}

    return [row for row in booked if row["id"] not in already_threaded_ids]


async def send_message(db: AsyncSession, thread: ChatThread, sender: User, content: str | None, file_path: str | None) -> ChatMessage:
    if not content and not file_path:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Сообщение не может быть пустым")
    message = ChatMessage(thread_id=thread.id, sender_id=sender.id, content=content, file_path=file_path)
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Notifications are tutor-facing (section 2.7); a message from the tutor themselves
    # doesn't need to notify the tutor.
    if sender.role == "student":
        await notification_service.notify_tutor(
            db,
            thread.tutor_id,
            NotificationEvent.NEW_MESSAGE,
            "Новое сообщение в чате",
            f"{sender.display_name}: {content}" if content else f"{sender.display_name} отправил(а) файл.",
        )
    return message


async def list_messages(db: AsyncSession, thread_id: uuid.UUID) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


async def mark_thread_read(db: AsyncSession, thread_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Called whenever a user fetches a thread's messages (see api/v1/chat.py::list_messages)
    - "having the thread open" is treated as reading it, there's no separate
    explicit "mark as read" action in the UI."""
    result = await db.execute(
        select(ChatThreadRead).where(ChatThreadRead.thread_id == thread_id, ChatThreadRead.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    now = utcnow()
    if row is not None:
        row.last_read_at = now
    else:
        db.add(ChatThreadRead(thread_id=thread_id, user_id=user_id, last_read_at=now))
    await db.commit()


async def get_unread_counts(db: AsyncSession, thread_ids: list[uuid.UUID], user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Number of messages in each thread that arrived after the user's last-read
    marker and weren't sent by the user themselves - powers the unread badges in the
    thread list (components/ChatPanel.vue)."""
    if not thread_ids:
        return {}
    reads_result = await db.execute(
        select(ChatThreadRead.thread_id, ChatThreadRead.last_read_at).where(
            ChatThreadRead.thread_id.in_(thread_ids), ChatThreadRead.user_id == user_id
        )
    )
    last_read = dict(reads_result.all())

    messages_result = await db.execute(
        select(ChatMessage.thread_id, ChatMessage.created_at).where(
            ChatMessage.thread_id.in_(thread_ids), ChatMessage.sender_id != user_id
        )
    )
    counts: dict[uuid.UUID, int] = dict.fromkeys(thread_ids, 0)
    for thread_id, created_at in messages_result.all():
        since = last_read.get(thread_id)
        if since is None or created_at > since:
            counts[thread_id] += 1
    return counts


async def get_total_unread_for_user(db: AsyncSession, user: User) -> int:
    """Sum of unread counts across every thread the user can see - powers the
    combined chat+system badge (see api/v1/notifications.py, components/UserMenu.vue,
    CabinetView.vue's "Чат" tab)."""
    if user.role == "tutor":
        profile = await tutor_service.get_profile_by_user_id(db, user.id)
        threads = await list_threads_for_tutor(db, profile.id)
    elif user.role == "student":
        threads = await list_threads_for_student(db, user.id)
    else:
        return 0
    counts = await get_unread_counts(db, [t.id for t in threads], user.id)
    return sum(counts.values())


async def get_last_messages(db: AsyncSession, thread_ids: list[uuid.UUID]) -> dict[uuid.UUID, ChatMessage]:
    """Most recent message per thread - powers the preview line/timestamp in the
    thread list and its sort order (most recently active thread first)."""
    if not thread_ids:
        return {}
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id.in_(thread_ids))
        .order_by(ChatMessage.thread_id, ChatMessage.created_at.desc())
    )
    out: dict[uuid.UUID, ChatMessage] = {}
    for message in result.scalars().all():
        out.setdefault(message.thread_id, message)
    return out
