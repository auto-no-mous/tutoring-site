from pydantic import BaseModel


class TutorStatsOut(BaseModel):
    total_lessons_held: int
    homeworks_done: int
    unique_students_this_month: int


class StudentStatsOut(BaseModel):
    lessons_completed: int
    homework_total: int
    homework_done: int
    homework_completion_rate: float
