import datetime as dt
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.identity import OAuthState, UserIdentity
from app.models.tutor import TutorProfile
from app.services import oauth_providers
from app.services.oauth_providers import OAuthProfile, VKClient, YandexClient
from app.utils.time import utcnow

VK_PROFILE = OAuthProfile(
    provider="vk",
    provider_user_id="777",
    email=None,
    first_name="Пётр",
    last_name="Петров",
)
YANDEX_PROFILE = OAuthProfile(
    provider="yandex",
    provider_user_id="1234567",
    email="ya-user@yandex.ru",
    first_name="Анна",
    last_name="Аннова",
    avatar_url="https://avatars.yandex.net/get-yapic/abc/islands-200",
)
# Провайдер вправе не отдать имя - тогда его спрашиваем в форме.
NAMELESS_PROFILE = OAuthProfile(
    provider="yandex",
    provider_user_id="7654321",
    email=None,
    first_name=None,
    last_name=None,
)


@pytest.fixture(autouse=True)
def configured_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Оба провайдера "настроены": без кред ручки отвечают 503 и до логики не доходят."""
    monkeypatch.setattr(settings, "vk_client_id", "vk-app-id")
    monkeypatch.setattr(settings, "vk_redirect_uri", None)
    monkeypatch.setattr(settings, "yandex_client_id", "ya-app-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "ya-secret")
    monkeypatch.setattr(settings, "yandex_redirect_uri", None)


def fake_profile(profile: OAuthProfile):
    """Подменяет поход в VK/Яндекс: реального обмена кода в тестах нет."""

    async def _fetch(self, code: str, code_verifier: str, device_id: str | None) -> OAuthProfile:
        return profile

    return _fetch


@pytest.fixture
def vk_returns(monkeypatch: pytest.MonkeyPatch):
    def _apply(profile: OAuthProfile = VK_PROFILE) -> None:
        monkeypatch.setattr(VKClient, "fetch_profile", fake_profile(profile))

    return _apply


@pytest.fixture
def yandex_returns(monkeypatch: pytest.MonkeyPatch):
    def _apply(profile: OAuthProfile = YANDEX_PROFILE) -> None:
        monkeypatch.setattr(YandexClient, "fetch_profile", fake_profile(profile))

    return _apply


async def start_flow(client: AsyncClient, provider: str, token: str | None = None, **body) -> str:
    """Начинает авторизацию и возвращает state из выданной ссылки."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = await client.post(f"/api/v1/auth/oauth/{provider}/start", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    auth_url = resp.json()["auth_url"]
    return parse_qs(urlparse(auth_url).query)["state"][0]


async def register_with_password(client: AsyncClient, email: str = "pwd@example.com") -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret1",
            "first_name": "Иван",
            "last_name": "Иванов",
            "role": "student",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_providers_list_reflects_configuration(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "yandex_client_secret", None)
    resp = await client.get("/api/v1/auth/oauth/providers")
    assert resp.status_code == 200, resp.text
    enabled = {item["provider"]: item["enabled"] for item in resp.json()}
    assert enabled == {"vk": True, "yandex": False}


async def test_start_builds_pkce_authorize_url(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/oauth/vk/start", json={})
    assert resp.status_code == 200, resp.text
    params = parse_qs(urlparse(resp.json()["auth_url"]).query)
    assert params["client_id"] == ["vk-app-id"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["redirect_uri"] == ["http://localhost:5173/oauth/vk/callback"]
    assert len(params["state"][0]) >= 32


async def test_start_rejects_external_redirect_target(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/oauth/vk/start", json={"redirect_to": "https://evil.example/steal"}
    )
    assert resp.status_code == 422
    resp = await client.post("/api/v1/auth/oauth/vk/start", json={"redirect_to": "//evil.example"})
    assert resp.status_code == 422


async def test_start_unconfigured_provider(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "vk_client_id", None)
    resp = await client.post("/api/v1/auth/oauth/vk/start", json={})
    assert resp.status_code == 503


async def test_first_login_registers_then_signs_in(client: AsyncClient, vk_returns) -> None:
    vk_returns()

    state = await start_flow(client, "vk")
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback",
        json={"code": "code-1", "state": state, "device_id": "device-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "signup_required"
    assert body["prefill"] == {
        "email": None,
        "first_name": "Пётр",
        "last_name": "Петров",
        "avatar_url": None,
    }

    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": body["signup_token"], "role": "tutor", "pd_consent": True},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()["user"]
    # Имя не спрашивали - оно пришло из VK.
    assert created["display_name"] == "Петров Пётр"
    assert created["auth_providers"] == ["vk"]
    # VK не отдал почту - аккаунт живёт без неё, и подтверждать нечего.
    assert created["email"] is None
    assert created["email_verified"] is False

    # Повторный вход тем же VK-аккаунтом ведёт в него же, без второго шага.
    state = await start_flow(client, "vk")
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback",
        json={"code": "code-2", "state": state, "device_id": "device-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "authenticated"
    assert body["user"]["id"] == created["id"]
    assert body["tokens"]["access_token"]


async def test_signup_without_consent_rejected(client: AsyncClient, vk_returns) -> None:
    vk_returns()
    state = await start_flow(client, "vk")
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback",
        json={"code": "c", "state": state, "device_id": "d"},
    )
    signup_token = resp.json()["signup_token"]

    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": signup_token, "role": "student", "pd_consent": False},
    )
    assert resp.status_code == 422


async def test_signup_token_cannot_be_used_twice(client: AsyncClient, vk_returns) -> None:
    vk_returns()
    state = await start_flow(client, "vk")
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state, "device_id": "d"}
    )
    payload = {"signup_token": resp.json()["signup_token"], "role": "student", "pd_consent": True}
    assert (await client.post("/api/v1/auth/oauth/complete", json=payload)).status_code == 201
    # Второе окно с тем же токеном не должно заводить дубль аккаунта.
    assert (await client.post("/api/v1/auth/oauth/complete", json=payload)).status_code == 409


async def test_yandex_email_verified_from_provider(client: AsyncClient, yandex_returns) -> None:
    yandex_returns()
    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    body = resp.json()
    assert body["prefill"]["email"] == "ya-user@yandex.ru"

    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": body["signup_token"], "role": "student", "pd_consent": True},
    )
    created = resp.json()["user"]
    assert created["email"] == "ya-user@yandex.ru"
    assert created["display_name"] == "Аннова Анна"
    # Почту подтвердил сам Яндекс, письмо со ссылкой не нужно.
    assert created["email_verified"] is True


async def test_existing_email_is_not_auto_merged(client: AsyncClient, yandex_returns) -> None:
    await register_with_password(client, email=YANDEX_PROFILE.email)
    yandex_returns()

    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    assert resp.status_code == 409
    assert "Способы входа" in resp.json()["detail"]


async def test_state_is_single_use(client: AsyncClient, vk_returns) -> None:
    vk_returns()
    state = await start_flow(client, "vk")
    first = await client.post(
        "/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state, "device_id": "d"}
    )
    assert first.status_code == 200
    replay = await client.post(
        "/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state, "device_id": "d"}
    )
    assert replay.status_code == 400


async def test_unknown_and_foreign_state_rejected(client: AsyncClient, vk_returns) -> None:
    vk_returns()
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback",
        json={"code": "c", "state": "never-issued", "device_id": "d"},
    )
    assert resp.status_code == 400

    # State, выданный для VK, не годится для колбэка Яндекса.
    state = await start_flow(client, "vk")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    assert resp.status_code == 400


async def test_expired_state_rejected(
    client: AsyncClient, db_session: AsyncSession, vk_returns
) -> None:
    vk_returns()
    state = await start_flow(client, "vk")
    stored = (
        await db_session.execute(select(OAuthState).where(OAuthState.state == state))
    ).scalar_one()
    stored.expires_at = utcnow() - dt.timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state, "device_id": "d"}
    )
    assert resp.status_code == 400


async def test_link_and_unlink_provider(client: AsyncClient, yandex_returns) -> None:
    yandex_returns()
    tokens = (await register_with_password(client))["tokens"]
    access = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    state = await start_flow(client, "yandex", token=access)
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "linked"

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["auth_providers"] == ["password", "yandex"]

    # Дальше в аккаунт можно зайти и Яндексом - без второго шага регистрации.
    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    assert resp.json()["status"] == "authenticated"

    resp = await client.delete("/api/v1/auth/me/identities/yandex", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["auth_providers"] == ["password"]

    resp = await client.delete("/api/v1/auth/me/identities/yandex", headers=headers)
    assert resp.status_code == 404


async def test_provider_account_cannot_be_linked_twice(
    client: AsyncClient, yandex_returns
) -> None:
    yandex_returns()
    first = await register_with_password(client, email="first@example.com")
    second = await register_with_password(client, email="second@example.com")

    state = await start_flow(client, "yandex", token=first["tokens"]["access_token"])
    assert (
        await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    ).status_code == 200

    state = await start_flow(client, "yandex", token=second["tokens"]["access_token"])
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    assert resp.status_code == 409


async def test_last_login_method_cannot_be_unlinked(client: AsyncClient, vk_returns) -> None:
    vk_returns()
    state = await start_flow(client, "vk")
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state, "device_id": "d"}
    )
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": resp.json()["signup_token"], "role": "student", "pd_consent": True},
    )
    access = resp.json()["tokens"]["access_token"]

    resp = await client.delete(
        "/api/v1/auth/me/identities/vk", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 409
    assert "единственный способ входа" in resp.json()["detail"]


async def test_vk_requires_device_id(client: AsyncClient) -> None:
    state = await start_flow(client, "vk")
    resp = await client.post("/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state})
    assert resp.status_code == 400
    assert "device_id" in resp.json()["detail"]


async def test_identity_row_records_provider_email(
    client: AsyncClient, db_session: AsyncSession, yandex_returns
) -> None:
    yandex_returns()
    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": resp.json()["signup_token"], "role": "student", "pd_consent": True},
    )
    identity = (await db_session.execute(select(UserIdentity))).scalar_one()
    assert identity.provider == "yandex"
    assert identity.provider_user_id == "1234567"
    assert identity.email == "ya-user@yandex.ru"


async def test_names_come_from_provider_not_from_client(client: AsyncClient, vk_returns) -> None:
    """Имя едет в подписанном токене, поэтому подставить в форму чужое не выйдет."""
    vk_returns()
    state = await start_flow(client, "vk")
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state, "device_id": "d"}
    )
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={
            "signup_token": resp.json()["signup_token"],
            "role": "student",
            "first_name": "Самозванец",
            "last_name": "Подставной",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["display_name"] == "Петров Пётр"


async def test_student_grade_saved_and_ignored_for_tutor(
    client: AsyncClient, vk_returns, yandex_returns
) -> None:
    vk_returns()
    state = await start_flow(client, "vk")
    resp = await client.post(
        "/api/v1/auth/oauth/vk/callback", json={"code": "c", "state": state, "device_id": "d"}
    )
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={
            "signup_token": resp.json()["signup_token"],
            "role": "student",
            "grade": 9,
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["grade"] == 9

    # Репетитору класс не положен, даже если поле прислали.
    yandex_returns()
    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={
            "signup_token": resp.json()["signup_token"],
            "role": "tutor",
            "grade": 7,
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["grade"] is None


async def test_missing_provider_name_is_asked_in_form(
    client: AsyncClient, yandex_returns
) -> None:
    yandex_returns(NAMELESS_PROFILE)
    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    body = resp.json()
    assert body["prefill"]["first_name"] is None

    # Без имени регистрация не проходит...
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": body["signup_token"], "role": "student", "pd_consent": True},
    )
    assert resp.status_code == 422

    # ...а с введённым вручную - проходит.
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={
            "signup_token": body["signup_token"],
            "role": "student",
            "first_name": "Мария",
            "last_name": "Иванова",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["display_name"] == "Иванова Мария"


async def test_tutor_avatar_imported_from_provider(
    client: AsyncClient,
    db_session: AsyncSession,
    yandex_returns,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    yandex_returns()
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    downloaded: list[str] = []

    async def fake_download(url: str) -> tuple[bytes, str]:
        downloaded.append(url)
        return b"fake-image-bytes", "image/png"

    monkeypatch.setattr(oauth_providers, "download_avatar", fake_download)

    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": resp.json()["signup_token"], "role": "tutor", "pd_consent": True},
    )
    assert resp.status_code == 201, resp.text

    assert downloaded == [YANDEX_PROFILE.avatar_url]
    created = resp.json()["user"]
    profile = (await db_session.execute(select(TutorProfile))).scalar_one()
    # Одна и та же картинка: аватар аккаунта и стартовое фото анкеты.
    assert profile.photo_url == created["photo_url"]
    assert profile.photo_url is not None and profile.photo_url.startswith("/files/user-photos/")
    saved = tmp_path / "user-photos" / profile.photo_url.rsplit("/", 1)[-1]
    assert saved.read_bytes() == b"fake-image-bytes"


async def test_registration_survives_broken_avatar(
    client: AsyncClient, db_session: AsyncSession, yandex_returns, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Фото - бонус: если провайдер его не отдал, аккаунт всё равно должен создаться."""
    yandex_returns()

    async def failing_download(url: str) -> tuple[bytes, str]:
        raise RuntimeError("CDN недоступен")

    monkeypatch.setattr(oauth_providers, "download_avatar", failing_download)

    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": resp.json()["signup_token"], "role": "tutor", "pd_consent": True},
    )
    assert resp.status_code == 201, resp.text
    profile = (await db_session.execute(select(TutorProfile))).scalar_one()
    assert profile.photo_url is None


async def test_avatar_from_foreign_host_is_dropped() -> None:
    """Ссылку на аватар отдаёт провайдер, то есть внешняя сторона: качать по ней
    что угодно нельзя."""
    client = YandexClient()
    assert client._trusted_avatar_url("https://avatars.yandex.net/get-yapic/1/islands-200")
    assert client._trusted_avatar_url("https://evil.example/pic.png") is None
    assert client._trusted_avatar_url("http://169.254.169.254/latest/meta-data") is None
    assert client._trusted_avatar_url(None) is None


async def test_student_gets_provider_avatar(
    client: AsyncClient, yandex_returns, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """У ученика анкеты нет, но аватар аккаунта ему тоже положен."""
    yandex_returns()
    monkeypatch.setattr(settings, "storage_dir", tmp_path)

    async def fake_download(url: str) -> tuple[bytes, str]:
        return b"student-avatar", "image/jpeg"

    monkeypatch.setattr(oauth_providers, "download_avatar", fake_download)

    state = await start_flow(client, "yandex")
    resp = await client.post("/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state})
    resp = await client.post(
        "/api/v1/auth/oauth/complete",
        json={"signup_token": resp.json()["signup_token"], "role": "student", "pd_consent": True},
    )
    assert resp.status_code == 201, resp.text
    photo_url = resp.json()["user"]["photo_url"]
    assert photo_url is not None and photo_url.startswith("/files/user-photos/")
    assert (tmp_path / "user-photos" / photo_url.rsplit("/", 1)[-1]).read_bytes() == b"student-avatar"
