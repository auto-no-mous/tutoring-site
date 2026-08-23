import datetime as dt

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_email_verification_token, create_password_reset_token
from app.models.user import User
from app.services import telegram_service


async def test_register_login_me_refresh(client: AsyncClient) -> None:
    register_payload = {
        "email": "student@example.com",
        "password": "supersecret1",
        "first_name": "Ivan",
        "last_name": "Ivanov",
        "role": "student",
        "pd_consent": True,
    }
    resp = await client.post("/api/v1/auth/register", json=register_payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == "student@example.com"
    assert body["user"]["role"] == "student"
    assert body["user"]["display_name"] == "Ivanov Ivan"
    access_token = body["tokens"]["access_token"]
    refresh_token = body["tokens"]["refresh_token"]

    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "student@example.com"

    resp = await client.post("/api/v1/auth/login", json={
        "email": "student@example.com",
        "password": "supersecret1",
    })
    assert resp.status_code == 200, resp.text

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200, resp.text
    new_tokens = resp.json()
    assert new_tokens["access_token"] != access_token

    # Old refresh token was rotated out and must now be rejected.
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


async def test_register_duplicate_email_rejected(client: AsyncClient) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "tutor",
        "pd_consent": True,
    }
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201

    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


async def test_register_without_consent_rejected(client: AsyncClient) -> None:
    payload = {
        "email": "noconsent@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": False,
    }
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    payload = {
        "email": "wrongpw@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    }
    await client.post("/api/v1/auth/register", json=payload)

    resp = await client.post("/api/v1/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "nope",
    })
    assert resp.status_code == 401


async def test_repeated_failed_logins_lock_account(client: AsyncClient) -> None:
    payload = {
        "email": "lockout@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    }
    await client.post("/api/v1/auth/register", json=payload)

    for _ in range(5):
        resp = await client.post("/api/v1/auth/login", json={"email": "lockout@example.com", "password": "nope"})
        assert resp.status_code == 401

    # 5th failure trips the lock - even the correct password is now rejected.
    locked_resp = await client.post(
        "/api/v1/auth/login", json={"email": "lockout@example.com", "password": "supersecret1"}
    )
    assert locked_resp.status_code == 429

    # A fresh account with a different email is unaffected.
    other_payload = {**payload, "email": "not-locked@example.com"}
    await client.post("/api/v1/auth/register", json=other_payload)
    other_resp = await client.post(
        "/api/v1/auth/login", json={"email": "not-locked@example.com", "password": "supersecret1"}
    )
    assert other_resp.status_code == 200


async def test_update_my_settings(client: AsyncClient) -> None:
    register_payload = {
        "email": "settings@example.com",
        "password": "supersecret1",
        "first_name": "Original",
        "last_name": "Name",
        "role": "student",
        "pd_consent": True,
    }
    resp = await client.post("/api/v1/auth/register", json=register_payload)
    access_token = resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    assert resp.json()["user"]["telegram_chat_id"] is None
    assert resp.json()["user"]["notification_channel"] == "both"

    patch_resp = await client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={
            "first_name": "Updated",
            "last_name": "Name",
            "patronymic": "Ivanovich",
            "timezone": "Europe/Samara",
            "telegram_chat_id": "123456789",
            "notification_channel": "telegram",
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["display_name"] == "Name Updated Ivanovich"
    assert body["timezone"] == "Europe/Samara"
    assert body["telegram_chat_id"] == "123456789"
    assert body["notification_channel"] == "telegram"


async def test_change_email_requires_reverification_and_rejects_duplicates(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json={
        "email": "taken@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    })

    resp = await client.post("/api/v1/auth/register", json={
        "email": "changeme@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    })
    headers = {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}

    conflict_resp = await client.patch("/api/v1/auth/me", headers=headers, json={"email": "taken@example.com"})
    assert conflict_resp.status_code == 409

    change_resp = await client.patch("/api/v1/auth/me", headers=headers, json={"email": "changed@example.com"})
    assert change_resp.status_code == 200, change_resp.text
    assert change_resp.json()["email"] == "changed@example.com"
    assert change_resp.json()["email_verified"] is False

    # New email now logs in; old one no longer does.
    old_login = await client.post("/api/v1/auth/login", json={"email": "changeme@example.com", "password": "supersecret1"})
    assert old_login.status_code == 401
    new_login = await client.post("/api/v1/auth/login", json={"email": "changed@example.com", "password": "supersecret1"})
    assert new_login.status_code == 200


async def test_verify_email_flow(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/register", json={
        "email": "verifyme@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    })
    user_id = resp.json()["user"]["id"]
    assert resp.json()["user"]["email_verified"] is False

    # Registration itself already issued a token and "sent" it (logged, since email
    # is disabled in tests) - a real user would click that link. We mint an
    # equivalent one here since we don't have the mailbox.
    token = create_email_verification_token(user_id)
    verify_resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["email_verified"] is True

    bad_resp = await client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert bad_resp.status_code == 400


async def test_resend_verification_email(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/register", json={
        "email": "resend@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    })
    user_id = resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}

    resend_resp = await client.post("/api/v1/auth/verify-email/resend", headers=headers)
    assert resend_resp.status_code == 204

    token = create_email_verification_token(user_id)
    await client.post("/api/v1/auth/verify-email", json={"token": token})

    already_verified_resp = await client.post("/api/v1/auth/verify-email/resend", headers=headers)
    assert already_verified_resp.status_code == 409


async def test_telegram_link_token_flow(client: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    # Isolate from whatever the developer running these tests has in their own
    # backend/.env (pydantic-settings loads it regardless of test context) - this
    # test specifically covers the "bot not configured" behavior.
    monkeypatch.setattr(telegram_service.settings, "telegram_bot_username", None)

    resp = await client.post("/api/v1/auth/register", json={
        "email": "tglink@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    })
    headers = {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}

    issue_resp = await client.post("/api/v1/auth/me/telegram-link-token", headers=headers)
    assert issue_resp.status_code == 200, issue_resp.text
    body = issue_resp.json()
    assert body["token"]
    # No TELEGRAM_BOT_USERNAME configured in tests - link is None, not a dead URL.
    assert body["deep_link"] is None

    # This is what the bot's /start handler does once the user opens the deep link.
    linked_user = await telegram_service.link_chat_by_token(db_session, body["token"], "555444333")
    assert linked_user is not None
    assert linked_user.telegram_chat_id == "555444333"

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.json()["telegram_chat_id"] == "555444333"

    # A used (now-cleared) token doesn't link a second time.
    reused = await telegram_service.link_chat_by_token(db_session, body["token"], "999")
    assert reused is None

    unknown = await telegram_service.link_chat_by_token(db_session, "not-a-real-token", "123")
    assert unknown is None


async def test_telegram_link_token_expiry(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.post("/api/v1/auth/register", json={
        "email": "tgexpired@example.com",
        "password": "supersecret1",
        "first_name": "T",
        "last_name": "T",
        "role": "student",
        "pd_consent": True,
    })
    headers = {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}
    token = (await client.post("/api/v1/auth/me/telegram-link-token", headers=headers)).json()["token"]

    result = await db_session.execute(select(User).where(User.telegram_link_token == token))
    user = result.scalar_one()
    user.telegram_link_token_expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    linked = await telegram_service.link_chat_by_token(db_session, token, "111")
    assert linked is None


async def test_password_reset_revokes_existing_refresh_tokens(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "resetflow@example.com",
            "password": "supersecret1",
            "first_name": "R",
            "last_name": "R",
            "role": "student",
            "pd_consent": True,
        },
    )
    body = register_resp.json()
    user_id = body["user"]["id"]
    old_refresh_token = body["tokens"]["refresh_token"]

    # Confirm the token works before the reset.
    pre_reset_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert pre_reset_refresh.status_code == 200, pre_reset_refresh.text
    old_refresh_token = pre_reset_refresh.json()["refresh_token"]

    reset_token = create_password_reset_token(user_id)
    confirm_resp = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "brandnewpassword1"},
    )
    assert confirm_resp.status_code == 204, confirm_resp.text

    # The refresh token issued before the reset must now be rejected, even though it
    # had not expired and was never itself used again after the pre-reset check above.
    post_reset_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert post_reset_refresh.status_code == 401

    # The new password works; the old one no longer does.
    old_login = await client.post(
        "/api/v1/auth/login", json={"email": "resetflow@example.com", "password": "supersecret1"}
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login", json={"email": "resetflow@example.com", "password": "brandnewpassword1"}
    )
    assert new_login.status_code == 200
