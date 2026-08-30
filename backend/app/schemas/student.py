import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.auth import TokenPair
from app.schemas.common import UTCDateTime
from app.schemas.user import UserOut


class ManagedStudentCreate(BaseModel):
    """Ученик, заведённый репетитором вручную. Ни почты, ни пароля здесь нет
    намеренно: их задаёт сам ученик, если однажды заберёт аккаунт себе."""

    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    grade: int | None = Field(default=None, ge=1, le=11)
    note: str | None = Field(default=None, max_length=2000)


class ManagedStudentUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    grade: int | None = Field(default=None, ge=1, le=11)


class StudentNoteUpdate(BaseModel):
    # Пустая строка убирает примечание - отдельной ручки удаления не нужно.
    text: str = Field(default="", max_length=2000)


class TutorStudentStatsOut(BaseModel):
    """Строка блока «Ученики» в статистике репетитора."""

    id: uuid.UUID
    first_name: str
    last_name: str
    patronymic: str | None
    grade: int | None
    photo_url: str | None
    # Заведён репетитором и ещё не забран учеником: только такого можно править и
    # удалять, и только для такого выдаётся ссылка-приглашение.
    is_managed: bool
    has_login: bool
    note: str | None
    lessons_held: int
    no_shows: int
    last_lesson_at: UTCDateTime | None
    next_lesson_at: UTCDateTime | None
    homework_done: int
    homework_pending: int


class ClaimLinkOut(BaseModel):
    url: str
    expires_at: UTCDateTime


class ClaimPreviewOut(BaseModel):
    """Что показывает страница по ссылке-приглашению до того, как человек решит, чем
    входить."""

    display_name: str
    grade: int | None
    tutor_display_name: str


class ClaimWithPasswordRequest(BaseModel):
    token: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # 152-ФЗ: согласие даёт сам человек в этот момент - репетитор, заводя профиль, за
    # него согласиться не мог.
    pd_consent: bool

    @field_validator("pd_consent")
    @classmethod
    def consent_must_be_given(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Согласие на обработку персональных данных обязательно")
        return v


class ClaimResponse(BaseModel):
    user: UserOut
    tokens: TokenPair
