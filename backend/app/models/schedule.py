import uuid

from sqlalchemy import ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPKMixin


class WeeklyAvailability(UUIDPKMixin, Base):
    """A tutor's recurring working interval on a given weekday.

    A tutor may have several intervals per weekday (e.g. 09:00-14:00 and 14:00-18:00).
    Times are stored in MSK (the canonical timezone for the tutor's schedule, see
    project_description.md sections 2.3 and 6 - the tutor cabinet always shows MSK).
    """

    __tablename__ = "weekly_availability"

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time: Mapped["Time"] = mapped_column(Time, nullable=False)
    end_time: Mapped["Time"] = mapped_column(Time, nullable=False)

    tutor: Mapped["TutorProfile"] = relationship(back_populates="availability_slots")  # noqa: F821
