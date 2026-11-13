"""Чат «Поддержка»: обращения пользователей и те, кто на них отвечает."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.services import notification_service
from app.utils.time import utcnow


async def _register(client: AsyncClient, email: str, role: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret1",
            "first_name": "Тест",
            "last_name": role,
            "role": role,
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {"headers": {"Authorization": f"Bearer {body['tokens']['access_token']}"}, "user": body["user"]}


async def _admin(client: AsyncClient, db_session: AsyncSession) -> dict:
    db_session.add(
        User(
            role="admin",
            email="support-admin@example.com",
            password_hash=hash_password("adminpass1"),
            display_name="Админ",
            email_verified=True,
            is_active=True,
            pd_consent_given=True,
            pd_consent_at=utcnow(),
        )
    )
    await db_session.commit()
    resp = await client.post("/api/v1/auth/login", json={"email": "support-admin@example.com", "password": "adminpass1"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def notified(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []

    async def fake_notify(db: Any, user_id: Any, event: Any, title: str, body: str, **kwargs: Any) -> None:
        sent.append((str(user_id), title))

    monkeypatch.setattr(notification_service, "notify", fake_notify)
    return sent


async def _threads(client: AsyncClient, headers: dict) -> list[dict]:
    resp = await client.get("/api/v1/chat/threads", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_user_writes_to_support_and_an_appointed_tutor_answers(
    client: AsyncClient, db_session: AsyncSession, notified: list
) -> None:
    admin = await _admin(client, db_session)
    student = await _register(client, "support-student@example.com", "student")
    helper = await _register(client, "support-helper@example.com", "tutor")
    outsider = await _register(client, "support-outsider@example.com", "tutor")

    # Админ назначает в поддержку аккаунт репетитора - по почте.
    added = await client.post("/api/v1/admin/support/staff", headers=admin, json={"email": "Support-Helper@example.com"})
    assert added.status_code == 200, added.text
    staff = (await client.get("/api/v1/admin/support/staff", headers=admin)).json()
    assert [s["id"] for s in staff] == [helper["user"]["id"]]
    me = (await client.get("/api/v1/auth/me", headers=helper["headers"])).json()
    assert me["answers_support"] is True

    # Ученик открывает «Поддержку» и пишет.
    thread = (await client.post("/api/v1/chat/threads/support", headers=student["headers"])).json()
    assert thread["type"] == "support"
    assert thread["display_title"] == "Поддержка"
    again = (await client.post("/api/v1/chat/threads/support", headers=student["headers"])).json()
    assert again["id"] == thread["id"], "обращение одно на человека"
    resp = await client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages", headers=student["headers"], data={"content": "Не открывается ДЗ"}
    )
    assert resp.status_code == 201, resp.text

    # Уведомление - всем, кто отвечает: админу и назначенному репетитору.
    recipients = {uid for uid, title in notified if title == "Новое обращение в поддержку"}
    assert helper["user"]["id"] in recipients
    assert len(recipients) == 2

    # Назначенный видит обращение в своём чате, с именем автора и непрочитанным.
    helper_threads = await _threads(client, helper["headers"])
    support = next(t for t in helper_threads if t["id"] == thread["id"])
    assert support["display_title"].startswith("Поддержка: ")
    assert support["unread_count"] == 1
    summary = (await client.get("/api/v1/notifications/unread-summary", headers=helper["headers"])).json()
    assert summary["chat_unread"] == 1

    # Посторонний репетитор - не видит и не может написать.
    assert all(t["id"] != thread["id"] for t in await _threads(client, outsider["headers"]))
    denied = await client.get(f"/api/v1/chat/threads/{thread['id']}/messages", headers=outsider["headers"])
    assert denied.status_code == 403

    # Ответ поддержки уходит автору обращения.
    notified.clear()
    resp = await client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages", headers=helper["headers"], data={"content": "Уже чиним"}
    )
    assert resp.status_code == 201, resp.text
    assert notified == [(student["user"]["id"], "Ответ поддержки my-tutor.ru")]
    messages = (await client.get(f"/api/v1/chat/threads/{thread['id']}/messages", headers=student["headers"])).json()
    assert [m["content"] for m in messages] == ["Не открывается ДЗ", "Уже чиним"]

    # Админ тоже видит обращения - в чате у него только они.
    admin_threads = await _threads(client, admin)
    assert [t["id"] for t in admin_threads] == [thread["id"]]

    # Сняли с поддержки - обращения больше не видны.
    removed = await client.delete(f"/api/v1/admin/support/staff/{helper['user']['id']}", headers=admin)
    assert removed.status_code == 204
    assert all(t["id"] != thread["id"] for t in await _threads(client, helper["headers"]))


async def test_support_staff_is_managed_by_admin_only(client: AsyncClient) -> None:
    tutor = await _register(client, "support-nosy@example.com", "tutor")
    resp = await client.post("/api/v1/admin/support/staff", headers=tutor["headers"], json={"email": "x@example.com"})
    assert resp.status_code == 403


async def test_unknown_email_is_reported(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _admin(client, db_session)
    resp = await client.post("/api/v1/admin/support/staff", headers=admin, json={"email": "nobody@example.com"})
    assert resp.status_code == 404
