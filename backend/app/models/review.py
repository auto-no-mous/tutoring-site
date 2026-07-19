import uuid

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class Review(UUIDPKMixin, TimestampMixin, Base):
    """One review per tutor-student pair, editable, requires a past lesson between them
    (section 10)."""

    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("tutor_id", "student_id", name="uq_review_tutor_student"),)

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
