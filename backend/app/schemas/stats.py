from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class TutorStatsOut(BaseModel):
    total_lessons_held: int
    homeworks_done: int
    unique_students_this_month: int


class StudentStatsOut(BaseModel):
    lessons_completed: int
    homework_total: int
    homework_done: int
    homework_completion_rate: float


class ActivityLogEntryOut(BaseModel):
    id: str
    event_type: str
    occurred_at: UTCDateTime
    lesson_at: UTCDateTime | None
    format_label: str
    counterpart_label: str
    counterpart_name: str
    duration_minutes: int | None
    status_label: str


class ActivityLogPageOut(BaseModel):
    entries: list[ActivityLogEntryOut]
    total: int
    page: int
    page_size: int
