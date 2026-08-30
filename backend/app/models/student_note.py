import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.utils.time import utcnow


class TutorStudentNote(UUIDPKMixin, Base):
    """Приватная заметка репетитора об ученике («повторить системы счисления»).

    Одна заметка на пару репетитор-ученик: это блокнот, а не переписка, и вести
    историю правок незачем. Ученику не показывается нигде - ни до, ни после того,
    как он заберёт аккаунт себе; наружу отдаётся только в списке учеников самого
    репетитора.
    """

    __tablename__ = "tutor_student_notes"
    __table_args__ = (
        UniqueConstraint("tutor_id", "student_id", name="uq_tutor_student_notes_pair"),
    )

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
