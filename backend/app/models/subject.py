import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class Subject(UUIDPKMixin, TimestampMixin, Base):
    """Admin-managed controlled vocabulary (e.g. "Математика", "Информатика") - tutors
    pick from this list instead of free-texting what they teach, so catalog search
    stays meaningful instead of accumulating near-duplicate spellings."""

    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    directions: Mapped[list["Direction"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", order_by="Direction.name"
    )


class Direction(UUIDPKMixin, TimestampMixin, Base):
    """A prep track within a subject (e.g. "Подготовка к ЕГЭ"), also admin-managed and
    scoped to its subject - some directions don't make sense for every subject (e.g.
    "Музыка" has no ЕГЭ), so the valid list is configured per subject rather than
    shared globally."""

    __tablename__ = "directions"
    __table_args__ = (UniqueConstraint("subject_id", "name", name="uq_direction_subject_name"),)

    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="directions")


class TutorSubject(UUIDPKMixin, TimestampMixin, Base):
    """A subject a given tutor teaches; a tutor may offer several subjects."""

    __tablename__ = "tutor_subjects"
    __table_args__ = (UniqueConstraint("tutor_id", "subject_id", name="uq_tutor_subject"),)

    tutor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)

    subject: Mapped["Subject"] = relationship()
    directions: Mapped[list["TutorSubjectDirection"]] = relationship(
        back_populates="tutor_subject", cascade="all, delete-orphan"
    )


class TutorSubjectDirection(UUIDPKMixin, Base):
    """Which of the subject's directions this tutor offers, e.g. Математика ->
    [5-9 класс, Подготовка к ОГЭ, Подготовка к ЕГЭ]."""

    __tablename__ = "tutor_subject_directions"
    __table_args__ = (
        UniqueConstraint("tutor_subject_id", "direction_id", name="uq_tutor_subject_direction"),
    )

    tutor_subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_subjects.id", ondelete="CASCADE"), index=True
    )
    direction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("directions.id", ondelete="CASCADE"), index=True)

    tutor_subject: Mapped["TutorSubject"] = relationship(back_populates="directions")
    direction: Mapped["Direction"] = relationship()
