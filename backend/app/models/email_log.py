import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.models.enums import EmailDirection, EmailKind, EmailStatus
from app.utils.time import utcnow


class EmailLog(UUIDPKMixin, Base):
    """Журнал писем сайта: транзакционные (подтверждение почты, сброс пароля),
    ручные письма администратора и входящие, которые принял наш Postfix.

    Отличается от NotificationLog: тот про доставку уведомлений пользователю по
    каналам (Telegram/почта) и привязан к событию, а этот - про сами письма,
    включая те, у которых нет пользователя в системе (входящие на info@).
    body_preview - начало текста для списка, body_text - весь текст, его админка
    подгружает по кнопке «Показать полностью». Полный текст понадобился, когда
    служебные адреса (postmaster@, abuse@, no-reply@) перестали пересылаться на личный
    ящик: журнал стал единственным местом, где эти письма можно прочитать. Только
    текст, без HTML: чужую разметку админка не отображает. У записей до 23.10.2026
    body_text пуст - тогда сохранялось только превью.
    """

    __tablename__ = "email_log"

    direction: Mapped[str] = mapped_column(String(8), default=EmailDirection.OUTBOUND.value, index=True)
    kind: Mapped[str] = mapped_column(String(24), default=EmailKind.OTHER.value, index=True)
    status: Mapped[str] = mapped_column(String(16), default=EmailStatus.SENT.value, index=True)
    address_from: Mapped[str] = mapped_column(String(320))
    address_to: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(512), default="")
    body_preview: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Получатель, если письмо адресовано пользователю сайта, и админ-отправитель
    # для писем, написанных руками из админки. ondelete=SET NULL: журнал переживает
    # удаление аккаунта, иначе пропадёт история отправок.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sent_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=None, default=utcnow, index=True
    )
