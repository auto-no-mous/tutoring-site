import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import AuthProvider, NotificationChannelPref
from app.models.identity import UserIdentity
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.tutor import TutorProfile


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # Nullable because social-login accounts may not expose an email (VK ID only returns
    # one if the user granted the scope), so such users are identified by their
    # app.models.identity.UserIdentity row rather than by email.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Brute-force protection (see auth_service.authenticate_user): counts consecutive
    # failed password attempts since the last success, reset to 0 on a successful
    # login. Once it reaches the threshold, locked_until is set and login is rejected
    # until that timestamp passes, regardless of the counter.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Denormalized full name, composed from the fields below at registration/settings-
    # update time (see app.utils.names.compose_display_name). Kept as the single
    # column most of the app reads (bookings, reviews, chat, notifications, ...) so
    # those call sites don't need to know about the first/last/patronymic split.
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    # Patronymic (отчество): mainly meaningful for tutors' formal ФИО, optional for
    # everyone since the field doesn't universally apply (e.g. social-login accounts).
    patronymic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # School grade (класс), e.g. 10 for "10-й класс". Only meaningful for students,
    # used to identify them in the tutor's homework-assignment student picker.
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Аватар аккаунта: показывается в шапке, а репетитору - в карточке его ученика.
    # Публичное фото анкеты репетитора живёт отдельно, в TutorProfile.photo_url: это
    # разные вещи по смыслу (одно человек ставит для себя, второе - витрина в
    # каталоге), и репетитор правит их в разных местах. При регистрации через
    # VK/Яндекс аватар провайдера кладётся сразу в оба места.
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
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
    # Куда слать уведомления и напоминания: off / email / telegram / both
    # (NotificationChannelPref). Письма о регистрации и сбросе пароля сюда не
    # относятся - они транзакционные и уходят всегда.
    notification_channel: Mapped[str] = mapped_column(
        String(16), default=NotificationChannelPref.BOTH.value, server_default=NotificationChannelPref.BOTH.value
    )
    # How long before a lesson this user wants the "Скоро занятие" reminder (see
    # notification_service.send_upcoming_reminders) - editable in Settings, next to
    # the Telegram connect button. Each participant of a booking has their own value,
    # so a tutor and student on the same lesson can be reminded at different times.
    reminder_lead_minutes: Mapped[int] = mapped_column(Integer, default=60)

    # Short-lived token for the "Подключить Telegram" deep-link flow (see
    # app.services.telegram_service.create_link_token / the bot's /start handler in
    # app.scripts.run_telegram_bot) - only one pending link attempt at a time, so this
    # lives directly on the user rather than in a separate table.
    telegram_link_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    telegram_link_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tutor_profile: Mapped["TutorProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # lazy="selectin": UserOut.auth_providers читается на каждом /auth/me, а ленивая
    # подгрузка в async-сессии падает (MissingGreenlet), так что грузим сразу.
    identities: Mapped[list["UserIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def auth_providers(self) -> list[str]:
        """Способы, которыми в этот аккаунт можно войти - для настроек и для проверки
        "не отвязываем ли мы последний" (см. oauth_service.unlink_identity)."""
        providers = [AuthProvider.PASSWORD.value] if self.password_hash else []
        providers.extend(sorted(identity.provider for identity in self.identities))
        return providers


class RefreshToken(UUIDPKMixin, Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=None, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
