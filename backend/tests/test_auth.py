from httpx import AsyncClient


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
    assert resp.json()["user"]["email_notifications_enabled"] is True

    patch_resp = await client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={
            "first_name": "Updated",
            "last_name": "Name",
            "patronymic": "Ivanovich",
            "timezone": "Europe/Samara",
            "telegram_chat_id": "123456789",
            "email_notifications_enabled": False,
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["display_name"] == "Name Updated Ivanovich"
    assert body["timezone"] == "Europe/Samara"
    assert body["telegram_chat_id"] == "123456789"
    assert body["email_notifications_enabled"] is False


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
