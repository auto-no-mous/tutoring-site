import uuid

from pydantic import BaseModel, ConfigDict, Field


class DirectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_id: uuid.UUID
    name: str


class DirectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class DirectionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    directions: list[DirectionOut] = Field(default_factory=list)


class SubjectCatalogOut(SubjectOut):
    """Public subject list. Carries how many catalog-visible tutors teach the subject
    so the home page can label its subject tiles and drop the ones nobody teaches."""

    tutors_count: int = 0


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class SubjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TutorSubjectSelection(BaseModel):
    """One subject the tutor teaches + the subject's directions they offer."""

    subject_id: uuid.UUID
    direction_ids: list[uuid.UUID] = Field(default_factory=list)


class TutorSubjectsReplace(BaseModel):
    selections: list[TutorSubjectSelection]


class TutorSubjectOut(BaseModel):
    subject_id: uuid.UUID
    subject_name: str
    directions: list[DirectionOut]
