"""Журнал почты и отправка писем из админки."""

from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.email_log import EmailLog
from app.models.enums import EmailDirection, EmailKind, EmailStatus
from app.models.user import User
from app.services import admin_service
from app.utils.time import utcnow


async def _register(client: AsyncClient, email: str, role: str) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret1",
            "first_name": "Test",
            "last_name": role,
            "role": role,
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {"headers": {"Authorization": f"Bearer {body['tokens']['access_token']}"}, "user": body["user"]}


async def _admin_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    admin = User(
        role="admin",
        email="mail-admin@example.com",
        password_hash=hash_password("adminpass1"),
        display_name="Admin",
        email_verified=True,
        is_active=True,
        pd_consent_given=True,
        pd_consent_at=utcnow(),
    )
    db_session.add(admin)
    await db_session.commit()
    resp = await client.post("/api/v1/auth/login", json={"email": admin.email, "password": "adminpass1"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_log(db_session: AsyncSession) -> None:
    now = utcnow()
    db_session.add_all(
        [
            EmailLog(
                direction=EmailDirection.OUTBOUND.value,
                kind=EmailKind.VERIFICATION.value,
                status=EmailStatus.SENT.value,
                address_from="no-reply@my-tutor.ru",
                address_to="student@example.com",
                subject="Подтверждение почты",
                body_preview="ссылка",
                created_at=now,
            ),
            EmailLog(
                direction=EmailDirection.OUTBOUND.value,
                kind=EmailKind.PASSWORD_RESET.value,
                status=EmailStatus.FAILED.value,
                address_from="no-reply@my-tutor.ru",
                address_to="broken@example.com",
                subject="Восстановление пароля",
                body_preview="ссылка",
                error="ConnectionRefusedError",
                created_at=now,
            ),
            EmailLog(
                direction=EmailDirection.INBOUND.value,
                kind=EmailKind.INBOUND.value,
                status=EmailStatus.RECEIVED.value,
                address_from="somebody@gmail.com",
                address_to="info@my-tutor.ru",
                subject="Вопрос про занятия",
                body_preview="здравствуйте",
                created_at=now,
            ),
            # Старее окна статистики (30 дней) - в счётчики попадать не должно.
            EmailLog(
                direction=EmailDirection.OUTBOUND.value,
                kind=EmailKind.VERIFICATION.value,
                status=EmailStatus.SENT.value,
                address_from="no-reply@my-tutor.ru",
                address_to="old@example.com",
                subject="Старое письмо",
                created_at=now - timedelta(days=45),
            ),
        ]
    )
    await db_session.commit()


async def test_email_log_requires_admin(client: AsyncClient) -> None:
    student = await _register(client, "mail-student0@example.com", "student")
    assert (await client.get("/api/v1/admin/emails", headers=student["headers"])).status_code == 403
    assert (await client.get("/api/v1/admin/emails")).status_code == 401


async def test_email_log_lists_and_filters(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session)
    await _seed_log(db_session)

    all_resp = await client.get("/api/v1/admin/emails", headers=headers)
    assert all_resp.status_code == 200, all_resp.text
    assert all_resp.json()["total"] == 4

    inbound = await client.get("/api/v1/admin/emails?direction=inbound", headers=headers)
    assert [e["address_to"] for e in inbound.json()["entries"]] == ["info@my-tutor.ru"]

    failed = await client.get("/api/v1/admin/emails?status=failed", headers=headers)
    assert failed.json()["entries"][0]["error"] == "ConnectionRefusedError"

    found = await client.get("/api/v1/admin/emails?q=broken@", headers=headers)
    assert found.json()["total"] == 1


async def test_email_stats_counts_window(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session)
    await _seed_log(db_session)

    stats = (await client.get("/api/v1/admin/emails/stats", headers=headers)).json()

    assert stats["sent_24h"] == 1
    assert stats["failed_24h"] == 1
    # Письмо 45-дневной давности за окно 30 дней не попадает.
    assert stats["sent_30d"] == 1
    assert stats["received_30d"] == 1
    assert stats["by_kind"] == {EmailKind.VERIFICATION.value: 1}


async def test_admin_sends_email_to_users(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await _admin_headers(client, db_session)
    student = await _register(client, "mail-student1@example.com", "student")
    calls: list[tuple[str, str, str]] = []

    async def fake_send(to: str, subject: str, body: str, **kwargs: Any) -> bool:
        calls.append((to, subject, body))
        return True

    monkeypatch.setattr(admin_service, "send_admin_email", fake_send)

    resp = await client.post(
        "/api/v1/admin/emails/send",
        headers=headers,
        json={
            "user_ids": [student["user"]["id"]],
            "emails": ["outsider@example.com"],
            "subject": "Важное сообщение",
            "body": "Первая строка\nВторая строка",
        },
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"sent": 2, "failed": 0, "skipped": []}
    # Каждому - отдельное письмо, чтобы получатели не видели адреса друг друга.
    assert sorted(call[0] for call in calls) == ["mail-student1@example.com", "outsider@example.com"]


async def test_admin_send_requires_recipients(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session)

    resp = await client.post(
        "/api/v1/admin/emails/send",
        headers=headers,
        json={"user_ids": [], "emails": [], "subject": "Тема", "body": "Текст"},
    )

    assert resp.status_code == 400


async def test_inbound_ingest_requires_token(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mail_ingest_token", "s3cret")
    payload = {
        "address_from": "somebody@gmail.com",
        "address_to": "info@my-tutor.ru",
        "subject": "Вопрос",
        "body_preview": "текст",
    }

    assert (await client.post("/api/v1/mail/inbound", json=payload)).status_code == 401
    wrong = await client.post("/api/v1/mail/inbound", json=payload, headers={"X-Mail-Ingest-Token": "nope"})
    assert wrong.status_code == 401


async def test_inbound_ingest_disabled_without_token(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "mail_ingest_token", None)

    resp = await client.post(
        "/api/v1/mail/inbound",
        json={"address_from": "a@b.c", "address_to": "info@my-tutor.ru", "subject": "", "body_preview": ""},
        headers={"X-Mail-Ingest-Token": "anything"},
    )

    assert resp.status_code == 401
