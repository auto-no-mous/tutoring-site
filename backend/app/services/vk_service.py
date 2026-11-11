"""Уведомления во ВКонтакте: личные сообщения от сообщества сайта.

Писать человеку в личку сообщество может, только если тот сам начал с ним диалог.
Поэтому привязка устроена как у Telegram: «Подключить ВКонтакте» в настройках выдаёт
короткий код и ссылку vk.me/<сообщество>?ref=<код>; человек жмёт «Начать», бот
сообщества (app.scripts.run_vk_bot) получает сообщение вместе с кодом и запоминает,
кому писать. Если ВК код через ссылку не передал, его можно просто отправить
сообщением - бот поймёт и так.
"""

import logging
import random
import re
import secrets
import string
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.user import NotificationSettings
from app.utils.time import ensure_aware, utcnow

logger = logging.getLogger("app.vk")

API_URL = "https://api.vk.com/method"
API_VERSION = "5.199"
# Как и у Telegram: код живёт, пока человек переходит в ВК и жмёт «Начать».
LINK_TOKEN_TTL = timedelta(minutes=15)
# Код короткий и без похожих символов: если ссылка его не донесёт, его вводят руками.
_CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1I")
_CODE_LENGTH = 8
_CODE_RE = re.compile(rf"\b([{_CODE_ALPHABET}]{{{_CODE_LENGTH}}})\b")


class VkApiError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"VK API error {code}: {message}")
        self.code = code


def is_configured() -> bool:
    return bool(settings.vk_enabled and settings.vk_group_token and settings.vk_group_id)


async def call(method: str, *, timeout: float = 10.0, **params: Any) -> Any:
    """Вызов метода API от имени сообщества. Ошибку ВК поднимает как VkApiError: в
    ответе на ошибку HTTP-статус всё равно 200."""
    data = {**params, "access_token": settings.vk_group_token, "v": API_VERSION}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{API_URL}/{method}", data=data)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        error = body["error"]
        raise VkApiError(int(error.get("error_code", 0)), str(error.get("error_msg", "")))
    return body.get("response")


async def send_vk_message(peer_id: str, text: str) -> None:
    """Личное сообщение от сообщества. Без настроек ВК (локальная разработка) - только
    в лог, как и у Telegram."""
    if not is_configured():
        logger.info("VK (not sent, disabled) to=%s\n%s", peer_id, text)
        return
    # random_id - защита от дублей: ВК не отправит повторно сообщение с тем же
    # значением, если запрос повторится.
    await call("messages.send", peer_id=peer_id, message=text, random_id=random.getrandbits(31))


def _new_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def create_link_code(db: AsyncSession, user: User) -> str:
    """Новый код привязки; прежний, если был, перестаёт действовать."""
    code = _new_code()
    user.vk_link_token = code
    user.vk_link_token_expires_at = utcnow() + LINK_TOKEN_TTL
    await db.commit()
    return code


def build_link_url(code: str) -> str | None:
    if not is_configured() or not settings.vk_group_screen_name:
        return None
    return f"https://vk.me/{settings.vk_group_screen_name}?ref={code}"


def extract_code(ref: str | None, text: str | None) -> str | None:
    """Код из параметра ref ссылки vk.me или из текста сообщения."""
    for source in (ref, text):
        if not source:
            continue
        match = _CODE_RE.search(source.upper())
        if match:
            return match.group(1)
    return None


async def link_peer_by_code(db: AsyncSession, code: str, peer_id: str) -> User | None:
    result = await db.execute(select(User).where(User.vk_link_token == code))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if user.vk_link_token_expires_at is None or ensure_aware(user.vk_link_token_expires_at) < utcnow():
        return None

    user.vk_peer_id = peer_id
    user.vk_link_token = None
    user.vk_link_token_expires_at = None
    # Подключили ВК - значит, хотят получать туда уведомления (как и с Telegram).
    prefs = NotificationSettings.model_validate(user.notification_settings or {})
    prefs.vk.enabled = True
    user.notification_settings = prefs.model_dump()
    await db.commit()
    await db.refresh(user)
    return user


async def unlink(db: AsyncSession, user: User) -> User:
    user.vk_peer_id = None
    user.vk_link_token = None
    user.vk_link_token_expires_at = None
    await db.commit()
    await db.refresh(user)
    return user


GREETING = (
    "Здравствуйте! Это уведомления my-tutor.ru. Чтобы получать их сюда, откройте "
    "«Настройки» на сайте и нажмите «Подключить ВКонтакте»."
)
BAD_CODE = "Код не подошёл или устарел. Получите новый в «Настройках» на сайте."


async def handle_incoming(db: AsyncSession, message: dict[str, Any]) -> str | None:
    """Ответ бота на входящее сообщение (событие message_new) или None - молчать.

    Отвечаем только в личке: в беседах сообщество привязку не делает."""
    peer_id = message.get("peer_id")
    from_id = message.get("from_id")
    if not peer_id or peer_id != from_id or peer_id >= 2_000_000_000:
        return None

    code = extract_code(message.get("ref"), message.get("text"))
    if code is None:
        # Уже подключённым не отвечаем: в диалогах сообщества с ними могут
        # переписываться и живые администраторы, автоответ им бы мешал.
        linked = await db.scalar(select(User.id).where(User.vk_peer_id == str(peer_id)).limit(1))
        return None if linked else GREETING

    user = await link_peer_by_code(db, code, str(peer_id))
    if user is None:
        return BAD_CODE
    return f"Готово, {user.first_name}! Теперь уведомления с my-tutor.ru будут приходить сюда."
