from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import TokenPair
from app.schemas.user import UserOut


class OAuthStartRequest(BaseModel):
    # Куда вернуть пользователя после успешного входа. Принимаем только путь внутри
    # сайта (валидатор ниже): подставленный сюда чужой адрес превратил бы вход в
    # открытый редирект.
    redirect_to: str | None = Field(default=None, max_length=512)

    @field_validator("redirect_to")
    @classmethod
    def only_internal_path(cls, v: str | None) -> str | None:
        if v is None:
            return None
        # "//host" браузер трактует как протокол-относительный абсолютный адрес,
        # поэтому мало проверить первый символ.
        if not v.startswith("/") or v.startswith("//"):
            raise ValueError("Допустим только путь внутри сайта")
        return v


class OAuthStartResponse(BaseModel):
    auth_url: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str
    # VK ID передаёт device_id в колбэке и требует его при обмене кода; у Яндекса
    # такого параметра нет.
    device_id: str | None = None


class OAuthSignupPrefill(BaseModel):
    """Что провайдер уже знает о человеке: показываем это на шаге регистрации, чтобы
    он видел, с какими данными заводится аккаунт. Имя и почта в самой регистрации
    берутся не отсюда, а из подписанного signup-токена."""

    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None


class OAuthCallbackResponse(BaseModel):
    # authenticated - вошли в существующий аккаунт;
    # signup_required - провайдер опознан, но аккаунта ещё нет: нужен второй шаг с
    #   ролью и согласием на обработку ПД (POST /auth/oauth/complete);
    # linked - привязали провайдера к аккаунту, из которого начали поток.
    status: Literal["authenticated", "signup_required", "linked"]
    user: UserOut | None = None
    tokens: TokenPair | None = None
    signup_token: str | None = None
    prefill: OAuthSignupPrefill | None = None
    redirect_to: str | None = None


class OAuthCompleteRequest(BaseModel):
    """Второй шаг регистрации через провайдера. Осознанно короткий: роль, класс для
    ученика и согласие на обработку ПД. ФИО, почта и фото приезжают из провайдера.

    Имя и фамилия остаются в запросе только как запасной вариант: провайдер вправе
    их не отдать (у Яндекса поля профиля могут быть пустыми), и тогда форма
    спрашивает их у пользователя - см. oauth_service.complete_signup."""

    signup_token: str
    role: Literal["tutor", "student"]
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    # Класс имеет смысл только для ученика; у репетитора поле игнорируется.
    grade: int | None = Field(default=None, ge=1, le=11)
    # 152-ФЗ: согласие обязательно и при регистрации через провайдера, ровно как при
    # обычной (см. RegisterRequest).
    pd_consent: bool

    @field_validator("pd_consent")
    @classmethod
    def consent_must_be_given(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Согласие на обработку персональных данных обязательно")
        return v


class OAuthProviderOut(BaseModel):
    provider: str
    label: str
    # False, когда на сервере не заданы креды приложения - фронтенд в этом случае не
    # показывает кнопку, вместо того чтобы вести человека в заведомо мёртвый поток.
    enabled: bool
