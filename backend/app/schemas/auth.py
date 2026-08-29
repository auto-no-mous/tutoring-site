from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserOut


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    # Patronymic (отчество): mainly used for tutors' formal ФИО, optional for everyone.
    patronymic: str | None = Field(default=None, max_length=255)
    role: Literal["tutor", "student"]
    # 152-FZ: consent to personal data processing, required at registration.
    pd_consent: bool

    @field_validator("pd_consent")
    @classmethod
    def consent_must_be_given(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Согласие на обработку персональных данных обязательно")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class EmailVerifyRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    user: UserOut
    tokens: TokenPair


class TelegramLinkTokenOut(BaseModel):
    token: str
    # None when the bot's @username isn't configured in settings yet.
    deep_link: str | None
