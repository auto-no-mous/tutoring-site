import datetime as dt

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.identity import UserIdentity
from app.models.user import User
from app.services.oauth_providers import OAuthProfile, YandexClient


async def _register(client: AsyncClient, email: str, role: str) -> dict:
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
    return {
        "user": body["user"],
        "headers": {"Authorization": f"Bearer {body['tokens']['access_token']}"},
    }


async def _create_student(client: AsyncClient, tutor: dict, **overrides) -> dict:
    payload = {"first_name": "Пётр", "last_name": "Петров", "grade": 9, **overrides}
    resp = await client.post("/api/v1/tutors/me/students", headers=tutor["headers"], json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_managed_student_has_no_way_in_until_claimed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register(client, "managed-tutor1@example.com", "tutor")
    student = await _create_student(client, tutor, patronymic="Петрович")

    assert student["is_managed"] is True
    assert student["has_login"] is False

    stored = await db_session.get(User, __import__("uuid").UUID(student["id"]))
    assert stored.role == "student"
    assert stored.email is None and stored.password_hash is None
    assert stored.display_name == "Петров Пётр Петрович"
    # Согласие на обработку ПД за человека никто не давал - оно появится, когда он
    # сам заберёт аккаунт.
    assert stored.pd_consent_given is False


async def test_managed_student_appears_in_pickers_before_any_lesson(
    client: AsyncClient,
) -> None:
    """Смысл всей затеи: выбрать такого ученика надо ещё до первой записи."""
    tutor = await _register(client, "managed-tutor2@example.com", "tutor")
    student = await _create_student(client, tutor)

    picker = (await client.get("/api/v1/tutors/me/students", headers=tutor["headers"])).json()
    assert [row["id"] for row in picker] == [student["id"]]
    assert picker[0]["last_lesson_at"] is None


async def test_stats_list_counts_lessons_and_keeps_note(client: AsyncClient) -> None:
    tutor = await _register(client, "managed-tutor3@example.com", "tutor")
    student = await _create_student(client, tutor, note="повторить системы счисления")

    rows = (await client.get("/api/v1/tutors/me/students/stats", headers=tutor["headers"])).json()
    assert len(rows) == 1
    assert rows[0]["note"] == "повторить системы счисления"
    assert rows[0]["lessons_held"] == 0
    assert rows[0]["next_lesson_at"] is None

    # Примечание можно поменять и снять пустой строкой.
    resp = await client.put(
        f"/api/v1/tutors/me/students/{student['id']}/note",
        headers=tutor["headers"],
        json={"text": "плохо с циклами"},
    )
    assert resp.status_code == 204, resp.text
    rows = (await client.get("/api/v1/tutors/me/students/stats", headers=tutor["headers"])).json()
    assert rows[0]["note"] == "плохо с циклами"

    await client.put(
        f"/api/v1/tutors/me/students/{student['id']}/note",
        headers=tutor["headers"],
        json={"text": "   "},
    )
    rows = (await client.get("/api/v1/tutors/me/students/stats", headers=tutor["headers"])).json()
    assert rows[0]["note"] is None


async def test_manual_booking_for_managed_student(client: AsyncClient) -> None:
    tutor = await _register(client, "managed-tutor4@example.com", "tutor")
    student = await _create_student(client, tutor)

    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    resp = await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={
            "student_id": student["id"],
            "start_at": start.isoformat(),
            "end_at": (start + dt.timedelta(minutes=60)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text

    rows = (await client.get("/api/v1/tutors/me/students/stats", headers=tutor["headers"])).json()
    assert rows[0]["next_lesson_at"] is not None


async def test_only_owner_can_edit_or_delete(client: AsyncClient) -> None:
    tutor = await _register(client, "managed-tutor5@example.com", "tutor")
    stranger = await _register(client, "managed-tutor6@example.com", "tutor")
    student = await _create_student(client, tutor)

    resp = await client.patch(
        f"/api/v1/tutors/me/students/{student['id']}",
        headers=stranger["headers"],
        json={"grade": 11},
    )
    assert resp.status_code == 404
    resp = await client.delete(
        f"/api/v1/tutors/me/students/{student['id']}", headers=stranger["headers"]
    )
    assert resp.status_code == 404

    resp = await client.patch(
        f"/api/v1/tutors/me/students/{student['id']}",
        headers=tutor["headers"],
        json={"grade": 11, "last_name": "Сидоров"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["grade"] == 11

    resp = await client.delete(
        f"/api/v1/tutors/me/students/{student['id']}", headers=tutor["headers"]
    )
    assert resp.status_code == 204
    rows = (await client.get("/api/v1/tutors/me/students/stats", headers=tutor["headers"])).json()
    assert rows == []


async def test_managed_student_can_be_added_to_group_directly(client: AsyncClient) -> None:
    """Заявку такой ученик подать не может - в аккаунт никто не входит."""
    tutor = await _register(client, "managed-tutor7@example.com", "tutor")
    student = await _create_student(client, tutor)
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
        )
    ).json()["id"]
    group_id = (
        await client.post(
            "/api/v1/groups",
            headers=tutor["headers"],
            json={
                "name": "Группа с виртуальным",
                "lesson_type_id": lesson_type_id,
                "capacity": 1,
                "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
            },
        )
    ).json()["id"]

    resp = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers=tutor["headers"],
        json={"student_id": student["id"]},
    )
    assert resp.status_code == 201, resp.text

    # Повторное добавление и переполнение группы отбиваются.
    resp = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers=tutor["headers"],
        json={"student_id": student["id"]},
    )
    assert resp.status_code == 409

    other = await _register(client, "managed-real-student@example.com", "student")
    resp = await client.post(
        f"/api/v1/groups/{group_id}/members",
        headers=tutor["headers"],
        json={"student_id": other["user"]["id"]},
    )
    # Обычного ученика так зачислить нельзя - только через его заявку.
    assert resp.status_code == 404


async def test_claim_with_password_keeps_history(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "claim-tutor1@example.com", "tutor")
    student = await _create_student(client, tutor)

    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={
            "student_id": student["id"],
            "start_at": start.isoformat(),
            "end_at": (start + dt.timedelta(minutes=60)).isoformat(),
        },
    )

    link = (
        await client.post(
            f"/api/v1/tutors/me/students/{student['id']}/claim-link", headers=tutor["headers"]
        )
    ).json()
    token = link["url"].rsplit("/", 1)[-1]

    preview = (await client.get(f"/api/v1/auth/claim/{token}")).json()
    assert preview["display_name"] == "Петров Пётр"
    assert preview["tutor_display_name"] == "tutor Test"

    resp = await client.post(
        "/api/v1/auth/claim/password",
        json={
            "token": token,
            "email": "claimed@example.com",
            "password": "supersecret1",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    claimed = resp.json()
    # Тот же самый аккаунт: id не поменялся, значит занятия и группы остались.
    assert claimed["user"]["id"] == student["id"]
    assert claimed["user"]["auth_providers"] == ["password"]

    headers = {"Authorization": f"Bearer {claimed['tokens']['access_token']}"}
    bookings = (await client.get("/api/v1/bookings/my", headers=headers)).json()
    assert len(bookings) == 1

    # Ссылка одноразовая, а аккаунт больше не управляется репетитором.
    assert (await client.get(f"/api/v1/auth/claim/{token}")).status_code == 404
    stored = await db_session.get(User, __import__("uuid").UUID(student["id"]))
    await db_session.refresh(stored)
    assert stored.managed_by_tutor_id is None
    assert stored.pd_consent_given is True

    rows = (await client.get("/api/v1/tutors/me/students/stats", headers=tutor["headers"])).json()
    assert rows[0]["is_managed"] is False
    assert rows[0]["has_login"] is True


async def test_claim_rejects_taken_email_and_expired_link(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register(client, "claim-tutor2@example.com", "tutor")
    existing = await _register(client, "already-here@example.com", "student")
    assert existing["user"]["email"] == "already-here@example.com"
    student = await _create_student(client, tutor)

    link = (
        await client.post(
            f"/api/v1/tutors/me/students/{student['id']}/claim-link", headers=tutor["headers"]
        )
    ).json()
    token = link["url"].rsplit("/", 1)[-1]

    resp = await client.post(
        "/api/v1/auth/claim/password",
        json={
            "token": token,
            "email": "already-here@example.com",
            "password": "supersecret1",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 409

    # Просроченная ссылка отличается от несуществующей: человеку надо сказать, что
    # дело в сроке, а не в опечатке.
    stored = await db_session.get(User, __import__("uuid").UUID(student["id"]))
    stored.claim_token_expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()
    assert (await client.get(f"/api/v1/auth/claim/{token}")).status_code == 410


async def test_claim_through_provider(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "yandex_client_id", "ya-app-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "ya-secret")

    async def fake_fetch(self, code: str, code_verifier: str, device_id: str | None) -> OAuthProfile:
        return OAuthProfile(
            provider="yandex",
            provider_user_id="claim-777",
            email="claimed-via-yandex@yandex.ru",
            first_name="Пётр",
            last_name="Петров",
        )

    monkeypatch.setattr(YandexClient, "fetch_profile", fake_fetch)

    tutor = await _register(client, "claim-tutor3@example.com", "tutor")
    student = await _create_student(client, tutor)
    link = (
        await client.post(
            f"/api/v1/tutors/me/students/{student['id']}/claim-link", headers=tutor["headers"]
        )
    ).json()
    token = link["url"].rsplit("/", 1)[-1]

    start = await client.post("/api/v1/auth/oauth/yandex/start", json={"claim_token": token})
    assert start.status_code == 200, start.text
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(start.json()["auth_url"]).query)["state"][0]

    resp = await client.post(
        "/api/v1/auth/oauth/yandex/callback", json={"code": "c", "state": state}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Не "linked", а полноценный вход: человек забрал аккаунт и должен сразу попасть внутрь.
    assert body["status"] == "authenticated"
    assert body["user"]["id"] == student["id"]
    assert body["user"]["auth_providers"] == ["yandex"]
    assert body["tokens"]["access_token"]


async def test_claim_start_rejects_unknown_token(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "yandex_client_id", "ya-app-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "ya-secret")
    resp = await client.post("/api/v1/auth/oauth/yandex/start", json={"claim_token": "nonsense"})
    assert resp.status_code == 404


async def test_managed_student_gets_no_system_notifications(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Копить непрочитанные в аккаунте, куда никто не заходит, бессмысленно."""
    tutor = await _register(client, "managed-tutor8@example.com", "tutor")
    student = await _create_student(client, tutor)
    identities = (await db_session.execute(select(UserIdentity))).scalars().all()
    assert identities == []

    from app.models.system_notification import SystemNotification

    notifications = (
        await db_session.execute(
            select(SystemNotification).where(
                SystemNotification.user_id == __import__("uuid").UUID(student["id"])
            )
        )
    ).scalars().all()
    assert notifications == []


async def _weekly_lesson_type(client: AsyncClient, tutor: dict) -> str:
    resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Индивидуальное", "format": "individual", "duration_minutes": 60, "price": 1000},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_tutor_assigns_weekly_series_outside_own_grid(client: AsyncClient) -> None:
    """Серия, назначенная репетитором, не должна упираться в его недельную сетку:
    иначе «каждый вторник в 18:00» дало бы одно занятие вместо серии."""
    tutor = await _register(client, "series-tutor1@example.com", "tutor")
    student = await _create_student(client, tutor)
    lesson_type_id = await _weekly_lesson_type(client, tutor)

    # Расписание репетитора пустое - ни одного интервала не заводим специально.
    start = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)).replace(
        minute=0, second=0, microsecond=0
    )
    resp = await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={
            "student_id": student["id"],
            "lesson_type_id": lesson_type_id,
            "start_at": start.isoformat(),
            "end_at": (start + dt.timedelta(minutes=60)).isoformat(),
            "repeat_weekly": True,
        },
    )
    assert resp.status_code == 201, resp.text

    bookings = (await client.get("/api/v1/bookings/tutor/me", headers=tutor["headers"])).json()
    # Первое занятие плюс сгенерированные повторы вперёд.
    assert len(bookings) > 1
    assert all(b["student_id"] == student["id"] for b in bookings)

    series = (await client.get("/api/v1/bookings/series/tutor", headers=tutor["headers"])).json()
    assert len(series) == 1
    assert series[0]["student_display_name"] == "Петров Пётр"
    assert series[0]["lesson_type_name"] == "Индивидуальное"
    assert series[0]["weekday"] == start.astimezone(
        __import__("zoneinfo").ZoneInfo("Europe/Moscow")
    ).weekday()


async def test_tutor_can_stop_series_of_managed_student(client: AsyncClient) -> None:
    """Ученик без аккаунта остановить серию не может - это делает репетитор."""
    tutor = await _register(client, "series-tutor2@example.com", "tutor")
    student = await _create_student(client, tutor)
    lesson_type_id = await _weekly_lesson_type(client, tutor)
    start = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).replace(
        minute=0, second=0, microsecond=0
    )
    await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={
            "student_id": student["id"],
            "lesson_type_id": lesson_type_id,
            "start_at": start.isoformat(),
            "end_at": (start + dt.timedelta(minutes=60)).isoformat(),
            "repeat_weekly": True,
        },
    )
    series = (await client.get("/api/v1/bookings/series/tutor", headers=tutor["headers"])).json()

    stranger = await _register(client, "series-tutor3@example.com", "tutor")
    resp = await client.post(
        f"/api/v1/bookings/series/{series[0]['id']}/stop", headers=stranger["headers"]
    )
    assert resp.status_code == 403

    resp = await client.post(
        f"/api/v1/bookings/series/{series[0]['id']}/stop", headers=tutor["headers"]
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False
    assert (await client.get("/api/v1/bookings/series/tutor", headers=tutor["headers"])).json() == []
