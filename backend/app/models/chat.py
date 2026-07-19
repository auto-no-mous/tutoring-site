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
    # Set for group threads; null for individual threads.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )

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
