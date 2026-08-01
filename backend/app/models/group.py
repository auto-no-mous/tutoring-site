import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Time as SATime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import (
    GroupApplicationStatus,
    GroupAttendanceOutcome,
    GroupMembershipStatus,
    GroupOccurrenceStatus,
)
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
    # Who ended the membership - BookedBy.STUDENT (left voluntarily) or .TUTOR
    # (removed); see group_service._leave. None while still active.
    left_by: Mapped[str | None] = mapped_column(String(16), nullable=True)

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


class GroupAttendance(UUIDPKMixin, TimestampMixin, Base):
    """Per-student result of a past group occurrence, set by the tutor (activity
    log). One row per (occurrence, student) who was an active member at the time -
    only created once the tutor records something other than the implicit CONDUCTED
    default, same lazy-write pattern as Booking.outcome."""

    __tablename__ = "group_attendances"
    __table_args__ = (UniqueConstraint("occurrence_id", "student_id", name="uq_group_attendance_occurrence_student"),)

    occurrence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("group_occurrences.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    outcome: Mapped[str] = mapped_column(String(32), default=GroupAttendanceOutcome.CONDUCTED.value)
