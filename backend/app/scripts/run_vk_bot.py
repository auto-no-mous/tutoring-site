"""Бот сообщества ВКонтакте: привязка «Подключить ВКонтакте» (Bots Long Poll API).

Как и бот Telegram, сам ходит в ВК за событиями, а не ждёт их на публичном адресе.
Его единственная работа - принять «Начать» (или код в сообщении) от человека,
пришедшего по ссылке из «Настроек», и запомнить, кому писать уведомления (см.
app.services.vk_service). Сами уведомления отправляет backend, этот процесс для
них не нужен.

В сообществе должен быть включён Long Poll API с событием «Входящее сообщение», а у
ключа доступа - права «Сообщения» и «Управление сообществом».

Usage:
    poetry run python -m app.scripts.run_vk_bot
"""

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services import vk_service

logger = logging.getLogger("app.vk.bot")

# ВК держит запрос открытым до 25 секунд, пока событий нет.
WAIT_SECONDS = 25


async def _server() -> dict[str, Any]:
    return await vk_service.call("groups.getLongPollServer", group_id=settings.vk_group_id)


async def _handle(update: dict[str, Any]) -> None:
    if update.get("type") != "message_new":
        return
    message = (update.get("object") or {}).get("message") or {}
    async with AsyncSessionLocal() as db:
        reply = await vk_service.handle_incoming(db, message)
    if reply:
        try:
            await vk_service.send_vk_message(str(message["peer_id"]), reply)
        except Exception:  # noqa: BLE001 - ответ не дошёл, но бот должен жить дальше
            logger.exception("VK bot: не удалось ответить peer_id=%s", message.get("peer_id"))


async def run_forever() -> None:
    """Если ВК не отвечает или отказывает (например, у ключа нет права на Long Poll),
    пробуем снова через минуту - без этого контейнер падал бы и перезапускался по
    кругу каждые несколько секунд."""
    while True:
        try:
            await run()
        except Exception:  # noqa: BLE001
            logger.exception("VK bot: Long Poll недоступен, следующая попытка через минуту")
            await asyncio.sleep(60)


async def run() -> None:
    server = await _server()
    ts = server["ts"]
    async with httpx.AsyncClient(timeout=WAIT_SECONDS + 10) as client:
        while True:
            try:
                resp = await client.get(
                    server["server"], params={"act": "a_check", "key": server["key"], "ts": ts, "wait": WAIT_SECONDS}
                )
                body = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("VK bot: сбой Long Poll (%s), переподключаюсь", exc)
                await asyncio.sleep(3)
                server = await _server()
                ts = server["ts"]
                continue

            # failed: 1 - устарел ts (берём новый из ответа), 2/3 - устарел ключ или
            # история: запрашиваем сервер заново.
            failed = body.get("failed")
            if failed == 1:
                ts = body["ts"]
                continue
            if failed:
                server = await _server()
                ts = server["ts"]
                continue

            ts = body["ts"]
            for update in body.get("updates", []):
                await _handle(update)


async def idle() -> None:
    # Контейнер бота поднимается вместе с остальными (профиль bot), и там, где ВК не
    # настроен, ему нечего делать. Выход здесь означал бы перезапуск по кругу.
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not vk_service.is_configured():
        print("VK bot: ВКонтакте не настроен (VK_ENABLED, VK_GROUP_TOKEN, VK_GROUP_ID в backend/.env) - жду.")
        asyncio.run(idle())
        return
    print("VK bot: запущен (Long Poll). Остановить - Ctrl+C.")
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
