import datetime as dt
import uuid

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.schemas.common import UTCDateTime


class AvailabilityIntervalIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: dt.time
    end_time: dt.time

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: dt.time, info: ValidationInfo) -> dt.time:
        start = info.data.get("start_time")
        if start is not None and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class AvailabilityIntervalOut(AvailabilityIntervalIn):
    id: uuid.UUID


class WeeklyAvailabilityReplace(BaseModel):
    intervals: list[AvailabilityIntervalIn]


class SlotOut(BaseModel):
    start_at: UTCDateTime
    end_at: UTCDateTime
    available: bool
