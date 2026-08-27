import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ChatThreadType
from app.utils.time import utcnow


class ChatThread(UUIDPKMixin, TimestampMixin, Base):
    """Either a 1:1 thread (tutor+student) or a group thread (all group members).

    A tutor-student pair always has exactly one individual thread, kept separate from
    any group thread they might also share (section 2.11: групповой чат отдельно от
    личных сообщений, которые остаются доступны всегда).
    """

    __tablename__ = "chat_threads"
    __table_args__ = (
        UniqueConstraint("tutor_id", "student_id", "type", name="uq_chat_thread_individual"),
    )

    type: Mapped[str] = mapped_column(String(16), default=ChatThreadType.INDIVIDUAL.value)
    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    # Set for individual threads; null for group threads.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Set for group threads; null for individual threads - and cleared again if the
    # group is deleted, since the chat deliberately outlives its group (see
    # group_service.delete_group). Hence SET NULL, not CASCADE: the correspondence
    # stays readable to the tutor as an archive.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Name the group had at the moment it was deleted. Written only then (a live group
    # is the better source, see api/v1/chat.py::_display_title), so that an archived
    # thread still has a heading in the chat list instead of an empty one.
    archived_group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(UUIDPKMixin, Base):
    __tablename__ = "chat_messages"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=None, default=utcnow, index=True)

    thread: Mapped["ChatThread"] = relationship(back_populates="messages")


class ChatThreadRead(UUIDPKMixin, Base):
    """Per-user last-read marker for a thread - powers unread badges/counts (see
    chat_service.get_unread_counts). Deliberately just one timestamp per (thread,
    user) pair rather than per-message read receipts - refreshed whenever that user
    fetches the thread's messages (chat_service.mark_thread_read)."""

    __tablename__ = "chat_thread_reads"
    __table_args__ = (UniqueConstraint("thread_id", "user_id", name="uq_chat_thread_read"),)

    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=None, default=utcnow)
