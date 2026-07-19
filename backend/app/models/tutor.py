import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base, TimestampMixin, UUIDPKMixin


class TutorProfile(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tutor_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # What the tutor prepares for is now structured (Subject/Direction, see
    # app.models.subject) rather than free text - see TutorSubject/TutorSubjectDirection.
    about: Mapped[str] = mapped_column(Text, default="")
    achievements: Mapped[str] = mapped_column(Text, default="")

    # Hidden from the public catalog, still reachable via direct link (section 2.1)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    # Schedule settings (section 2.3), shared across the tutor's whole schedule.
    slot_granularity_minutes: Mapped[int] = mapped_column(
        Integer, default=settings.default_slot_granularity_minutes
    )
    # Assumption: a single break duration applied after every lesson tutor-wide (spec
    # gives break as a schedule-level setting alongside granularity/lead time, section 2.3).
    break_between_lessons_minutes: Mapped[int] = mapped_column(Integer, default=0)
    min_lead_time_hours: Mapped[int] = mapped_column(
        Integer, default=settings.default_min_lead_time_hours
    )

    # Cancellation policy (section 2.5), individual lessons only.
    cancel_min_hours_before: Mapped[int] = mapped_column(Integer, default=24)
    cancel_max_per_month: Mapped[int] = mapped_column(Integer, default=4)

    # Reschedule policy (section 2.5), independent from cancellation policy.
    reschedule_min_hours_before: Mapped[int] = mapped_column(Integer, default=24)
    reschedule_max_per_month: Mapped[int] = mapped_column(Integer, default=4)

    user: Mapped["User"] = relationship(back_populates="tutor_profile")  # noqa: F821
    lesson_types: Mapped[list["LessonType"]] = relationship(  # noqa: F821
        back_populates="tutor", cascade="all, delete-orphan"
    )
    availability_slots: Mapped[list["WeeklyAvailability"]] = relationship(  # noqa: F821
        back_populates="tutor", cascade="all, delete-orphan"
    )
