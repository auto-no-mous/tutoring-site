import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import HomeworkContentType, HomeworkSubmissionMode, HomeworkSubmissionStatus


class HomeworkAssignment(UUIDPKMixin, TimestampMixin, Base):
    """A homework sent to a single student or to a whole group at once (section 2.8, 2.11).

    Exactly one of student_id / group_id is set.
    """

    __tablename__ = "homework_assignments"

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_profiles.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Optional - the create form's "Название задания" has no required-ness, since the
    # content (link/file) already identifies the assignment well enough on its own.
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(16), default=HomeworkContentType.LINK.value)
    content_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Whether the student must upload a file back or just tick "done" - tutor's choice
    # (sections 2.8, 3.2).
    submission_mode: Mapped[str] = mapped_column(
        String(16), default=HomeworkSubmissionMode.MARK_DONE.value
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submissions: Mapped[list["HomeworkSubmission"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class HomeworkSubmission(UUIDPKMixin, TimestampMixin, Base):
    """Per-student tracking of an assignment (one row per student, even for group
    assignments - section 2.11: "выполнение отслеживается по каждому ученику
    отдельно")."""

    __tablename__ = "homework_submissions"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("homework_assignments.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=HomeworkSubmissionStatus.PENDING.value)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment: Mapped["HomeworkAssignment"] = relationship(back_populates="submissions")
