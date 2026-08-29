"""Адаптеры внешних провайдеров входа: VK ID и Яндекс ID.

Здесь только разговор с провайдером - построить ссылку авторизации и обменять код
на профиль. Всё, что касается наших аккаунтов (state, привязка, регистрация), живёт
в app.services.oauth_service.

Различие протоколов, из-за которого адаптеры не сведены в один:
- VK ID это OAuth 2.1: PKCE обязателен и заменяет client_secret, плюс в обмене кода
  участвует device_id, который VK кладёт в колбэк рядом с code. Прежний протокол
  oauth.vk.com (client_secret + GET access_token) VK отключил 30.09.2025.
- Яндекс ID это обычный OAuth 2.0 с client_secret; PKCE ему не отправляем, чтобы не
  зависеть от того, включён ли он в настройках приложения.
"""

import base64
import hashlib
import logging
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.enums import AuthProvider

logger = logging.getLogger("app.oauth")

HTTP_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class OAuthProfile:
    """То, что мы забираем у провайдера: устойчивый идентификатор аккаунта и данные,
    которыми можно предзаполнить форму регистрации."""

    provider: str
    provider_user_id: str
    email: str | None
    first_name: str | None
    last_name: str | None
    # Ссылка на аватар у провайдера. Мы её не храним, а скачиваем картинку к себе
    # при регистрации репетитора (см. oauth_service._import_avatar): внешний адрес
    # в профиле означал бы и утечку визитов на CDN провайдера, и битое фото, когда
    # пользователь сменит аватар.
    avatar_url: str | None = None


def generate_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) по RFC 7636, метод S256."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class OAuthClient(ABC):
    name: str
    label: str
    # Хосты, с которых мы готовы скачивать аватар. Ссылка приходит в ответе
    # провайдера, то есть по сути извне, и без проверки хоста скачивание по ней
    # превратилось бы в SSRF-примитив (запрос из контейнера по произвольному адресу).
    avatar_hosts: tuple[str, ...] = ()

    @property
    @abstractmethod
    def is_configured(self) -> bool: ...

    @property
    @abstractmethod
    def redirect_uri(self) -> str: ...

    @abstractmethod
    def authorize_url(self, state: str, code_challenge: str) -> str: ...

    @abstractmethod
    async def fetch_profile(
        self, code: str, code_verifier: str, device_id: str | None
    ) -> OAuthProfile: ...

    def ensure_configured(self) -> None:
        if not self.is_configured:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"Вход через {self.label} не настроен на сервере",
            )

    def _trusted_avatar_url(self, url: str | None) -> str | None:
        """Пропускает только https-ссылки с известных хостов провайдера."""
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return None
        host = parsed.hostname or ""
        if any(host == allowed or host.endswith(f".{allowed}") for allowed in self.avatar_hosts):
            return url
        logger.warning("OAUTH: %s прислал аватар с неожиданного хоста %s", self.label, host)
        return None

    def _default_redirect_uri(self) -> str:
        base = settings.frontend_base_url.rstrip("/")
        return f"{base}/oauth/{self.name}/callback"

    async def _post(self, url: str, **kwargs: Any) -> dict:
        return await self._request("POST", url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict:
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as http_client:
                response = await http_client.request(method, url, **kwargs)
        except httpx.HTTPError:
            logger.exception("OAUTH: %s недоступен (%s)", self.label, url)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"{self.label} сейчас недоступен, попробуйте позже"
            )

        try:
            data = response.json()
        except ValueError:
            data = {}

        if response.status_code != 200 or "error" in data:
            # Ответ провайдера пишем в лог, но наружу не отдаём: там бывают подробности
            # вроде client_id и внутренних причин отказа, пользователю бесполезные.
            logger.warning(
                "OAUTH: %s ответил %s на %s: %s", self.label, response.status_code, url, data
            )
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Не удалось войти через {self.label}")
        return data


class VKClient(OAuthClient):
    name = AuthProvider.VK.value
    label = "VK ID"

    AUTHORIZE_URL = "https://id.vk.ru/authorize"
    TOKEN_URL = "https://id.vk.ru/oauth2/auth"
    USER_INFO_URL = "https://id.vk.ru/oauth2/user_info"
    SCOPE = "vkid.personal_info email"
    # Аватары VK раздаются с sunN-M.userapi.com.
    avatar_hosts = ("userapi.com", "vk.com")

    @property
    def is_configured(self) -> bool:
        return bool(settings.vk_client_id)

    @property
    def redirect_uri(self) -> str:
        return settings.vk_redirect_uri or self._default_redirect_uri()

    def authorize_url(self, state: str, code_challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": settings.vk_client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": self.SCOPE,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def fetch_profile(
        self, code: str, code_verifier: str, device_id: str | None
    ) -> OAuthProfile:
        if not device_id:
            # device_id VK кладёт в колбэк рядом с code, и без него обмен невозможен.
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "VK не передал device_id")

        token_data = await self._post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "client_id": settings.vk_client_id,
                "device_id": device_id,
                "redirect_uri": self.redirect_uri,
            },
        )
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "VK ID не вернул токен доступа")

        info = await self._post(
            self.USER_INFO_URL,
            data={"client_id": settings.vk_client_id, "access_token": access_token},
        )
        user = info.get("user") or {}
        user_id = user.get("user_id") or token_data.get("user_id")
        if not user_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "VK ID не вернул идентификатор пользователя"
            )

        return OAuthProfile(
            provider=self.name,
            provider_user_id=str(user_id),
            # Почту VK отдаёт, только если пользователь дал на неё право, так что
            # аккаунт без почты здесь - нормальный случай (User.email nullable).
            email=user.get("email") or token_data.get("email"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            avatar_url=self._trusted_avatar_url(user.get("avatar")),
        )


class YandexClient(OAuthClient):
    name = AuthProvider.YANDEX.value
    label = "Яндекс ID"

    AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
    TOKEN_URL = "https://oauth.yandex.ru/token"
    USER_INFO_URL = "https://login.yandex.ru/info"
    avatar_hosts = ("avatars.yandex.net",)
    # Размер аватара из набора Яндекса: 200x200 достаточно для карточки репетитора,
    # где фото показывается небольшим квадратом.
    AVATAR_TEMPLATE = "https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"

    @property
    def is_configured(self) -> bool:
        return bool(settings.yandex_client_id and settings.yandex_client_secret)

    @property
    def redirect_uri(self) -> str:
        return settings.yandex_redirect_uri or self._default_redirect_uri()

    def authorize_url(self, state: str, code_challenge: str) -> str:
        # Права (login:email, login:info) заданы в настройках приложения на
        # oauth.yandex.ru, отдельным параметром их не запрашиваем.
        params = {
            "response_type": "code",
            "client_id": settings.yandex_client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def fetch_profile(
        self, code: str, code_verifier: str, device_id: str | None
    ) -> OAuthProfile:
        token_data = await self._post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.yandex_client_id,
                "client_secret": settings.yandex_client_secret,
                "redirect_uri": self.redirect_uri,
            },
        )
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Яндекс ID не вернул токен доступа")

        info = await self._request(
            "GET",
            self.USER_INFO_URL,
            params={"format": "json"},
            headers={"Authorization": f"OAuth {access_token}"},
        )
        user_id = info.get("id")
        if not user_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Яндекс ID не вернул идентификатор пользователя"
            )

        # is_avatar_empty=true означает заглушку-болванку вместо фотографии - её
        # тащить к себе незачем.
        avatar_id = info.get("default_avatar_id")
        avatar_url = (
            self.AVATAR_TEMPLATE.format(avatar_id=avatar_id)
            if avatar_id and not info.get("is_avatar_empty")
            else None
        )

        return OAuthProfile(
            provider=self.name,
            provider_user_id=str(user_id),
            email=info.get("default_email"),
            first_name=info.get("first_name"),
            last_name=info.get("last_name"),
            avatar_url=self._trusted_avatar_url(avatar_url),
        )


# Аватары у VK и Яндекса - небольшие jpeg/png; всё, что заметно больше, почти
# наверняка не то, что мы просили, и тянуть это в storage не нужно.
MAX_AVATAR_BYTES = 5 * 1024 * 1024


async def download_avatar(url: str) -> tuple[bytes, str] | None:
    """Скачивает аватар по уже проверенной ссылке. Возвращает (содержимое,
    content-type) либо None, если провайдер ответил не картинкой или ответ слишком
    велик. Ошибки сети наружу не пробрасываются: фото - приятный бонус к
    регистрации, но не повод её сорвать."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        logger.warning("OAUTH: не удалось скачать аватар %s", url, exc_info=True)
        return None

    content_type = (response.headers.get("content-type") or "").split(";")[0].strip()
    if response.status_code != 200 or len(response.content) > MAX_AVATAR_BYTES:
        logger.warning(
            "OAUTH: аватар не забрали: статус=%s размер=%s", response.status_code, len(response.content)
        )
        return None
    return response.content, content_type


_CLIENTS: dict[str, OAuthClient] = {client.name: client for client in (VKClient(), YandexClient())}


def get_client(provider: str) -> OAuthClient:
    client = _CLIENTS.get(provider)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Неизвестный провайдер входа")
    return client


def all_clients() -> list[OAuthClient]:
    return list(_CLIENTS.values())
