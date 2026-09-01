import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ProfileUrl, UTCDateTime


class WhiteboardCreate(BaseModel):
    # Ровно одно из двух: доска пары репетитор-ученик либо доска группы.
    student_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    # ProfileUrl, а не просто строка: ссылка рендерится как <a href> в карточке
    # занятия, и javascript:/data: туда попасть не должны.
    url: ProfileUrl
    # Нужна, только когда досок несколько; у единственной обычно пусто, и карточка
    # подписывает её просто «Доска».
    title: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def exactly_one_owner(self) -> "WhiteboardCreate":
        if (self.student_id is None) == (self.group_id is None):
            raise ValueError("Укажите либо ученика, либо группу")
        return self


class WhiteboardUpdate(BaseModel):
    url: ProfileUrl | None = None
    title: str | None = Field(default=None, max_length=120)


class WhiteboardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    student_id: uuid.UUID | None
    group_id: uuid.UUID | None
    url: str
    title: str | None
    # По нему список отсортирован: сверху доска, которую открывали последней.
    last_used_at: UTCDateTime
