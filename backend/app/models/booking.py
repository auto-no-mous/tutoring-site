import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Time as SATime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import BookedBy, BookingStatus


class RecurringSeries(UUIDPKMixin, TimestampMixin, Base):
    """Weekly-recurring individual booking series (section 2.4).

    Stopping a series only prevents future bookings from being generated; already
    created upcoming bookings are left untouched and follow normal cancel/reschedule
    rules (section 3.1).
    """

    __tablename__ = "recurring_series"

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson_types.id", ondelete="CASCADE"))

    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time: Mapped[time] = mapped_column(SATime, nullable=False)  # MSK, canonical tutor schedule tz

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="recurring_series")


class Booking(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    # Nullable: a tutor may create a manual reserve/block with no student attached yet
    # (section 2.4).
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lesson_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lesson_types.id", ondelete="SET NULL"), nullable=True
    )

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(String(32), default=BookingStatus.SCHEDULED.value, index=True)
    is_manual_block: Mapped[bool] = mapped_column(Boolean, default=False)
    booked_by: Mapped[str] = mapped_column(String(16), default=BookedBy.STUDENT.value)

    # Set by the tutor after the lesson time has passed (activity log). None means
    # "not yet recorded" - the log/UI default a past scheduled booking to CONDUCTED
    # without requiring a write, so the tutor only needs to act on exceptions.
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Per-student link to the external meeting resource (section 2.6).
    meeting_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set once the "upcoming lesson" reminder notification has been sent (section
    # 2.7), so a periodically-run reminder job doesn't re-notify the same booking.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recurring_series_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recurring_series.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Also doubles as the "superseded at/by" marker when status becomes RESCHEDULED
    # (booking_service.reschedule_booking_by_student): who/when this row stopped being
    # the live booking, whether because it was cancelled or replaced by a reschedule.
    cancelled_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True
    )

    recurring_series: Mapped["RecurringSeries | None"] = relationship(back_populates="bookings")
