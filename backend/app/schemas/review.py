import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDateTime


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str | None = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    student_id: uuid.UUID
    rating: int
    text: str | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    student_display_name: str = ""


class RatingSummary(BaseModel):
    average: float | None
    count: int
