import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDateTime


class GroupScheduleSlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: dt.time


class GroupScheduleSlotOut(GroupScheduleSlotIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    lesson_type_id: uuid.UUID
    capacity: int = Field(gt=0)
    meeting_link: str | None = None
    schedule_slots: list[GroupScheduleSlotIn] = Field(default_factory=list)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0)
    meeting_link: str | None = None
    is_active: bool | None = None


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    lesson_type_id: uuid.UUID
    name: str
    capacity: int
    meeting_link: str | None
    is_active: bool
    schedule_slots: list[GroupScheduleSlotOut] = Field(default_factory=list)
    member_count: int = 0
    created_at: UTCDateTime
    # From the group's own lesson type - lets the frontend render periodicity like
    # "Среда 14:00, 90 мин" without a second round-trip (see app/api/v1/groups.py::_to_group_out).
    duration_minutes: int = 0


class GroupPublicOut(BaseModel):
    id: uuid.UUID
    tutor_id: uuid.UUID
    name: str
    capacity: int
    member_count: int
    price: float
    duration_minutes: int
    schedule_slots: list[GroupScheduleSlotOut]
    # Состояние текущего ученика по отношению к группе - чтобы страница групп
    # репетитора сразу показывала неактивную кнопку с понятной подписью, а не давала
    # нажать её и получить отказ. Для гостя и репетитора всегда False.
    is_member: bool = False
    has_pending_application: bool = False


class GroupApplicationCreate(BaseModel):
    message: str | None = None


class GroupApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    message: str | None
    created_at: UTCDateTime
    decided_at: UTCDateTime | None
    # Populated only where the group/tutor context isn't already implicit from the
    # request (e.g. a student's own "my applications" list) - see app/api/v1/groups.py.
    group_name: str = ""
    tutor_display_name: str = ""
    # Populated on the tutor-facing applicant list (see app/api/v1/groups.py::list_applications).
    student_display_name: str = ""


class GroupMembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    joined_at: UTCDateTime
    left_at: UTCDateTime | None
    left_by: str | None = None
    group_name: str = ""
    tutor_display_name: str = ""
    # Populated on the tutor-facing member list (see app/api/v1/groups.py::list_members).
    student_display_name: str = ""


class GroupOccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    start_at: UTCDateTime
    end_at: UTCDateTime
    status: str
    original_start_at: UTCDateTime | None


class GroupOccurrenceUpdate(BaseModel):
    start_at: UTCDateTime | None = None
    end_at: UTCDateTime | None = None
    status: str | None = None


class GroupOccurrenceCreate(BaseModel):
    start_at: UTCDateTime
    end_at: UTCDateTime


class StudentGroupOccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    start_at: UTCDateTime
    end_at: UTCDateTime
    status: str
    original_start_at: UTCDateTime | None
    group_name: str = ""
    tutor_display_name: str = ""
    meeting_link: str | None = None
    # Set once the student has declared they won't attend this specific occurrence
    # (see group_service.mark_own_no_show) - lets the card show that state instead of
    # the "Отменить" button.
    my_attendance_outcome: str | None = None


class GroupAttendanceEntryOut(BaseModel):
    student_id: uuid.UUID
    student_display_name: str
    outcome: str


class GroupAttendanceEntryIn(BaseModel):
    student_id: uuid.UUID
    outcome: str


class GroupAttendanceReplace(BaseModel):
    entries: list[GroupAttendanceEntryIn]
