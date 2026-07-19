import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LessonTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    format: Literal["individual", "group"]
    duration_minutes: int = Field(gt=0)
    price: float = Field(ge=0)


class LessonTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    duration_minutes: int | None = Field(default=None, gt=0)
    price: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class LessonTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    name: str
    format: str
    duration_minutes: int
    price: float
    is_active: bool
