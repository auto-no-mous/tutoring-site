"""Уведомления во ВКонтакте: привязка через бота сообщества и отправка."""

import datetime as dt
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import NotificationEvent
from app.models.user import User
from app.services import notification_service, vk_service
from app.utils.time import utcnow


@pytest.fixture
def vk_on(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """ВК «настроен», а вызовы API перехватываются."""
    calls: list[dict[str, Any]] = []

    async def fake_call(method: str, **params: Any) -> Any:
        calls.append({"method": method, **params})
        return 1

    monkeypatch.setattr(settings, "vk_enabled", True)
    monkeypatch.setattr(settings, "vk_group_token", "token")
    monkeypatch.setattr(settings, "vk_group_id", 194021787)
    monkeypatch.setattr(settings, "vk_group_screen_name", "mytutorru")
    monkeypatch.setattr(vk_service, "call", fake_call)
    return calls


async def _user(db: AsyncSession, **fields: Any) -> User:
    fields.setdefault("notification_settings", {"vk": {"enabled": False}})
    user = User(
        role="student",
        email="vk-user@example.com",
        display_name="Анна Иванова",
        first_name="Анна",
        last_name="Иванова",
        is_active=True,
        **fields,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def test_code_is_found_in_the_link_ref_or_in_the_text() -> None:
    assert vk_service.extract_code("ABCD2345", "Начать") == "ABCD2345"
    assert vk_service.extract_code(None, "мой код: abcd2345 ") == "ABCD2345"
    assert vk_service.extract_code(None, "Начать") is None
    assert vk_service.extract_code(None, None) is None


async def test_start_with_the_code_links_the_account_and_turns_the_channel_on(
    db_session: AsyncSession, vk_on: list
) -> None:
    user = await _user(db_session)
    code = await vk_service.create_link_code(db_session, user)
    assert vk_service.build_link_url(code) == f"https://vk.me/mytutorru?ref={code}"

    reply = await vk_service.handle_incoming(
        db_session, {"peer_id": 777, "from_id": 777, "text": "Начать", "ref": code}
    )
    assert reply is not None and "Анна" in reply

    await db_session.refresh(user)
    assert user.vk_peer_id == "777"
    assert user.vk_link_token is None
    assert user.notification_settings["vk"]["enabled"] is True


async def test_bad_or_expired_code_is_refused(db_session: AsyncSession, vk_on: list) -> None:
    user = await _user(db_session)
    code = await vk_service.create_link_code(db_session, user)
    user.vk_link_token_expires_at = utcnow() - dt.timedelta(minutes=1)
    await db_session.commit()

    reply = await vk_service.handle_incoming(db_session, {"peer_id": 5, "from_id": 5, "text": code})
    assert reply == vk_service.BAD_CODE
    await db_session.refresh(user)
    assert user.vk_peer_id is None


async def test_bot_greets_strangers_and_stays_quiet_with_linked_users_and_chats(
    db_session: AsyncSession, vk_on: list
) -> None:
    await _user(db_session, vk_peer_id="42")

    assert await vk_service.handle_incoming(db_session, {"peer_id": 9, "from_id": 9, "text": "привет"}) == (
        vk_service.GREETING
    )
    # С подключёнными могут переписываться администраторы - автоответа нет.
    assert await vk_service.handle_incoming(db_session, {"peer_id": 42, "from_id": 42, "text": "спасибо"}) is None
    # Беседы не трогаем.
    assert (
        await vk_service.handle_incoming(db_session, {"peer_id": 2_000_000_001, "from_id": 9, "text": "x"}) is None
    )


async def test_notifications_go_to_vk_when_linked_and_enabled(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[str, str]] = []

    async def fake_send(peer_id: str, text: str) -> None:
        sent.append((peer_id, text))

    async def fake_email(*args: Any, **kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(notification_service, "send_vk_message", fake_send)
    monkeypatch.setattr(notification_service, "send_email", fake_email)
    user = await _user(db_session, vk_peer_id="555", notification_settings={"vk": {"enabled": True}})

    await notification_service.notify(db_session, user.id, NotificationEvent.NEW_BOOKING, "Новая запись", "Завтра в 10:00")
    assert sent == [("555", "Новая запись\n\nЗавтра в 10:00")]

    user.notification_settings = {"vk": {"enabled": True, "new_booking": False}}
    await db_session.commit()
    await notification_service.notify(db_session, user.id, NotificationEvent.NEW_BOOKING, "Новая запись", "x")
    assert len(sent) == 1


async def test_send_uses_the_community_api(vk_on: list) -> None:
    await vk_service.send_vk_message("123", "Текст")
    assert vk_on[0]["method"] == "messages.send"
    assert vk_on[0]["peer_id"] == "123"
    assert vk_on[0]["message"] == "Текст"
    assert "random_id" in vk_on[0]


async def _register(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "vk-api@example.com",
            "password": "supersecret1",
            "first_name": "Пётр",
            "last_name": "Петров",
            "role": "student",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def test_link_and_disconnect_endpoints(client: AsyncClient, db_session: AsyncSession, vk_on: list) -> None:
    headers = await _register(client)
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["vk_connected"] is False
    assert me["notification_settings"]["vk"]["enabled"] is True

    link = await client.post("/api/v1/auth/me/vk-link", headers=headers)
    assert link.status_code == 200, link.text
    code = link.json()["code"]
    assert link.json()["link"] == f"https://vk.me/mytutorru?ref={code}"

    await vk_service.handle_incoming(db_session, {"peer_id": 31, "from_id": 31, "text": code})
    assert (await client.get("/api/v1/auth/me", headers=headers)).json()["vk_connected"] is True

    # Вписать чужой адрес через общие настройки нельзя - поля там нет.
    await client.patch("/api/v1/auth/me", headers=headers, json={"vk_peer_id": "999"})
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert "vk_peer_id" not in me

    off = await client.delete("/api/v1/auth/me/vk", headers=headers)
    assert off.status_code == 200, off.text
    assert off.json()["vk_connected"] is False


async def test_link_is_none_when_vk_is_not_configured(client: AsyncClient) -> None:
    headers = await _register(client)
    link = await client.post("/api/v1/auth/me/vk-link", headers=headers)
    assert link.status_code == 200
    assert link.json()["link"] is None
