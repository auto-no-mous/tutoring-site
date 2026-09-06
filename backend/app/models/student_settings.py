import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.utils.time import utcnow


class TutorStudentSettings(UUIDPKMixin, Base):
    """Что репетитор держит про конкретного ученика: приватная заметка и постоянная
    ссылка на занятие.

    Одна строка на пару репетитор-ученик. Заметка - блокнот («повторить системы
    счисления»), ученику она не показывается нигде: ни до, ни после того, как он
    заберёт аккаунт себе.

    Постоянная ссылка живёт здесь, а не только в самих занятиях, потому что «сделать
    ссылку постоянной» - свойство пары, а не разовая операция над списком. Пока она
    была разовой, ссылка проставлялась только в занятия, существовавшие на тот
    момент: вторая еженедельная серия, новые недели и самостоятельные записи ученика
    появлялись уже пустыми, и репетитор вводил её заново.
    """

    __tablename__ = "tutor_student_settings"
    __table_args__ = (
        UniqueConstraint("tutor_id", "student_id", name="uq_tutor_student_settings_pair"),
    )

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
