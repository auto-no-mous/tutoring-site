import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import LessonFormat


class LessonType(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "lesson_types"

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(16), default=LessonFormat.INDIVIDUAL.value)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Price per lesson (individual) or per seat (group), see section 2.2.
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tutor: Mapped["TutorProfile"] = relationship(back_populates="lesson_types")  # noqa: F821
