import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.tutor import TutorProfile


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # Nullable because VK-only accounts may not expose an email (see project_description.md
    # section 10: VK OAuth doesn't always return email, so VK users are identified by vk_id).
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    vk_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)

    # Denormalized full name, composed from the fields below at registration/settings-
    # update time (see app.utils.names.compose_display_name). Kept as the single
    # column most of the app reads (bookings, reviews, chat, notifications, ...) so
    # those call sites don't need to know about the first/last/patronymic split.
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    # Patronymic (отчество): mainly meaningful for tutors' formal ФИО, optional for
    # everyone since the field doesn't universally apply (e.g. VK-only accounts).
    patronymic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Section 6: student's timezone, auto-detected with manual override. Stored as an
    # IANA timezone name (e.g. "Europe/Moscow"). Not meaningful for tutors, whose cabinet
    # always renders in MSK regardless (section 2.3), so tutors keep the default.
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")

    # 152-FZ: consent to personal data processing, required at registration.
    pd_consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    pd_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Notification channel settings (section 2.7)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    tutor_profile: Mapped["TutorProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(UUIDPKMixin, Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=None, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
