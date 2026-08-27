import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base, TimestampMixin, UUIDPKMixin


class TutorProfile(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tutor_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Optional custom nickname for a pretty public profile URL
    # (my-tutor.ru/tutors/<slug>), settable after registration - see
    # tutor_service.update_profile for format/uniqueness validation and
    # get_profile_by_id_or_slug for the lookup side.
    slug: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    # What the tutor prepares for is now structured (Subject/Direction, see
    # app.models.subject) rather than free text - see TutorSubject/TutorSubjectDirection.
    # Rich text (bold/italic/underline/links), sanitized on the frontend before render.
    # Used to have a separate `achievements` field; merged into `about` (see migration
    # add_grade_to_users_merge_achievements_into_about) since both were free-form text
    # about the tutor and having two boxes was confusing.
    about: Mapped[str] = mapped_column(Text, default="")

    # Hidden from the public catalog, still reachable via direct link (section 2.1)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    # Contact links shown on the public profile (section on making the profile more
    # attractive/informative). Telegram/VK/YouTube are the three explicitly requested
    # channels, kept as dedicated columns since every tutor is expected to have at
    # most one of each; extra_links covers anything else (personal site, Instagram,
    # WhatsApp, ...) as an open-ended list.
    telegram_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vk_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra_links: Mapped[list[dict]] = mapped_column(JSON, default=list)

    # A single presentation video shown on the public profile. Stored exactly as the
    # tutor pasted it (so the edit form shows them their own link back); the embeddable
    # form is derived on read - see app.utils.video.parse_video_embed_url, which is
    # also what validates it on write.
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

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

    # Whether each booking channel is open on the public profile - see
    # api/v1/tutors.py::get_public_profile, which additionally requires at least one
    # active lesson type of the matching format before actually showing the booking
    # button (a tutor can't turn a channel on if they have nothing to book there - see
    # the disabled-toggle logic in components/tutor/ScheduleTab.vue). Default true so
    # existing tutors keep today's unrestricted behavior until they opt out.
    allow_individual_bookings: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_group_bookings: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="tutor_profile")  # noqa: F821
    lesson_types: Mapped[list["LessonType"]] = relationship(  # noqa: F821
        back_populates="tutor", cascade="all, delete-orphan"
    )
    availability_slots: Mapped[list["WeeklyAvailability"]] = relationship(  # noqa: F821
        back_populates="tutor", cascade="all, delete-orphan"
    )
