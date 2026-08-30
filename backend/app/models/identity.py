import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPKMixin
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.user import User


class UserIdentity(UUIDPKMixin, Base):
    """Аккаунт во внешнем провайдере (VK ID, Яндекс ID), привязанный к пользователю.

    Отдельная таблица, а не колонки users.vk_id/users.yandex_id: провайдеров уже
    два, к одному аккаунту можно привязать оба (плюс пароль), и список способов
    входа нужен целиком - см. User.auth_providers и раздел "Способы входа" в
    настройках. Пара (provider, provider_user_id) уникальна: один и тот же VK-аккаунт
    не может вести в два разных аккаунта на сайте.
    """

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_user_identities_provider_user"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # app.models.enums.AuthProvider: vk / yandex ("password" там же, но он не
    # идентичность, а наличие users.password_hash).
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Почта, которую провайдер отдал в момент привязки. Хранится справочно (для
    # поддержки: "каким аккаунтом входил"), логин по ней не идёт - опознаём строго
    # по provider_user_id, потому что почту в VK/Яндексе можно сменить.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="identities")


class OAuthState(UUIDPKMixin, Base):
    """Одноразовый state для OAuth-редиректа: связывает начало авторизации
    (/auth/oauth/{provider}/start) с колбэком, куда пользователь возвращается уже
    из VK/Яндекса.

    Живёт в базе, а не в памяти процесса: за nginx крутится несколько воркеров
    gunicorn, и колбэк почти наверняка попадёт не в тот воркер, который выдавал
    state. Строка удаляется при первом же использовании - повторно предъявленный
    state недействителен (защита от replay), просроченные подчищаются при выдаче
    следующего (см. oauth_service.create_state).
    """

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    # PKCE (RFC 7636): проверочная строка, парная code_challenge из ссылки авторизации.
    # Для VK ID она вместо client_secret, поэтому утечка этой таблицы = возможность
    # обменять перехваченный код.
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    # Куда вернуть пользователя во фронтенде после успешного входа.
    redirect_to: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Заполнен, если поток запущен из настроек залогиненным пользователем, который
    # привязывает провайдера к существующему аккаунту, а не входит. Он же заполняется
    # при получении аккаунта по ссылке-приглашению - там привязка авторизуется
    # одноразовым токеном вместо сессии, см. is_claim ниже.
    link_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    # True для ссылки-приглашения: после привязки провайдера аккаунт перестаёт быть
    # управляемым репетитором, а человек сразу получает сессию (в отличие от привязки
    # из настроек, где он уже залогинен).
    is_claim: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
