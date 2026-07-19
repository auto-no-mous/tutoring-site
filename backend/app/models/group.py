import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Time as SATime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import GroupApplicationStatus, GroupMembershipStatus, GroupOccurrenceStatus
from app.utils.time import utcnow


class Group(UUIDPKMixin, TimestampMixin, Base):
    """A preparation group (section 2.11), based on a group-format LessonType."""

    __tablename__ = "groups"

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    lesson_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson_types.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Single meeting link shared by all participants (section 2.11).
    meeting_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    schedule_slots: Mapped[list["GroupSchedule"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["GroupMembership"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    applications: Mapped[list["GroupApplication"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    occurrences: Mapped[list["GroupOccurrence"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupSchedule(UUIDPKMixin, Base):
    """Recurring weekly time slots for a group, e.g. "вторник и четверг, 18:00".

    Set by the tutor only - students never choose group timing (section 2.11).
    Times are stored in MSK, consistent with WeeklyAvailability/RecurringSeries.
    """

    __tablename__ = "group_schedule_slots"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time: Mapped[time] = mapped_column(SATime, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="schedule_slots")


class GroupApplication(UUIDPKMixin, TimestampMixin, Base):
    """A student's request to join a group; enrollment is a manual tutor decision
    (section 2.11 - no waitlist, no self-enrollment)."""

    __tablename__ = "group_applications"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=GroupApplicationStatus.PENDING.value)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group: Mapped["Group"] = relationship(back_populates="applications")


class GroupMembership(UUIDPKMixin, TimestampMixin, Base):
    """Once enrolled, a student is attached to all future group occurrences
    automatically, until they leave (section 2.11)."""

    __tablename__ = "group_memberships"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=GroupMembershipStatus.ACTIVE.value)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=None, default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group: Mapped["Group"] = relationship(back_populates="memberships")


class GroupOccurrence(UUIDPKMixin, TimestampMixin, Base):
    """A concrete dated group session, generated from GroupSchedule. The tutor keeps
    full CRUD over individual occurrences (cancel/reschedule a single date, section
    2.11)."""

    __tablename__ = "group_occurrences"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=GroupOccurrenceStatus.SCHEDULED.value)
    original_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group: Mapped["Group"] = relationship(back_populates="occurrences")
