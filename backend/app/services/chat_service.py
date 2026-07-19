import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatThread
from app.models.enums import ChatThreadType, GroupMembershipStatus, NotificationEvent
from app.models.group import GroupMembership
from app.models.user import User
from app.services import notification_service, tutor_service


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
