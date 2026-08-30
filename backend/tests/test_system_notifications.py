import datetime as dt
import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.system_notification import SystemNotification
from app.models.user import User
from app.utils.time import utcnow


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
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}
    return {"headers": headers, "user": body["user"]}


async def _admin_headers(client: AsyncClient, db_session: AsyncSession, email: str = "admin@example.com") -> dict:
    admin = User(
        role="admin",
        email=email,
        password_hash=hash_password("adminpass1"),
        display_name="Admin",
        email_verified=True,
        is_active=True,
        pd_consent_given=True,
        pd_consent_at=utcnow(),
    )
    db_session.add(admin)
    await db_session.commit()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _events_for_user(db_session: AsyncSession, user_id: str) -> list[str]:
    result = await db_session.execute(
        select(SystemNotification).where(SystemNotification.user_id == uuid.UUID(user_id))
    )
    return [n.event_type for n in result.scalars().all()]


async def _notification_body(db_session: AsyncSession, user_id: str, event_type: str) -> str:
    result = await db_session.execute(
        select(SystemNotification).where(
            SystemNotification.user_id == uuid.UUID(user_id),
            SystemNotification.event_type == event_type,
        )
    )
    return result.scalars().first().body


async def _setup_individual_booking(client: AsyncClient, tutor: dict, student: dict) -> dict:
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]
    await client.put(
        "/api/v1/tutors/me/availability",
        headers=tutor["headers"],
        json={"intervals": [{"weekday": 0, "start_time": "00:00:00", "end_time": "23:45:00"}]},
    )
    start_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8)
    days_to_monday = (0 - start_at.weekday()) % 7
    start_at = (start_at + dt.timedelta(days=days_to_monday)).replace(hour=10, minute=0, second=0, microsecond=0)

    resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor_id, "lesson_type_id": lesson_type_id, "start_at": start_at.isoformat()},
    )
    assert resp.status_code == 201, resp.text
    booking = resp.json()
    return {"tutor_id": tutor_id, "lesson_type_id": lesson_type_id, "booking": booking}


async def test_registration_sends_welcome_notification(client: AsyncClient, db_session: AsyncSession) -> None:
    student = await _register(client, "sysnotif-welcome@example.com", "student")
    events = await _events_for_user(db_session, student["user"]["id"])
    assert "welcome" in events


async def test_login_success_and_failure_notify(client: AsyncClient, db_session: AsyncSession) -> None:
    student = await _register(client, "sysnotif-login@example.com", "student")
    user_id = student["user"]["id"]

    # Registration itself doesn't log the user in via /auth/login, so no login_success
    # notification should exist yet - only the welcome message from registration.
    events = await _events_for_user(db_session, user_id)
    assert "login_success" not in events

    ok_resp = await client.post(
        "/api/v1/auth/login", json={"email": "sysnotif-login@example.com", "password": "supersecret1"}
    )
    assert ok_resp.status_code == 200, ok_resp.text
    events = await _events_for_user(db_session, user_id)
    assert "login_success" in events

    bad_resp = await client.post(
        "/api/v1/auth/login", json={"email": "sysnotif-login@example.com", "password": "wrongpassword"}
    )
    assert bad_resp.status_code == 401
    events = await _events_for_user(db_session, user_id)
    assert "login_failed" in events


async def test_individual_booking_cancel_notifies_both_directions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register(client, "sysnotif-tutor-cancel@example.com", "tutor")
    student = await _register(client, "sysnotif-student-cancel@example.com", "student")
    ctx = await _setup_individual_booking(client, tutor, student)

    resp = await client.post(
        f"/api/v1/bookings/{ctx['booking']['id']}/cancel", headers=student["headers"], json={}
    )
    assert resp.status_code == 200, resp.text
    tutor_events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "booking_cancelled_by_student" in tutor_events

    # Fresh booking for the tutor-cancels direction.
    ctx2 = await _setup_individual_booking(client, tutor, student)
    resp = await client.post(
        f"/api/v1/bookings/{ctx2['booking']['id']}/cancel", headers=tutor["headers"], json={}
    )
    assert resp.status_code == 200, resp.text
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "booking_cancelled_by_tutor" in student_events


async def test_individual_booking_reschedule_notifies_both_directions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register(client, "sysnotif-tutor-resched@example.com", "tutor")
    student = await _register(client, "sysnotif-student-resched@example.com", "student")
    ctx = await _setup_individual_booking(client, tutor, student)
    start_at = dt.datetime.fromisoformat(ctx["booking"]["start_at"])
    # Availability only covers weekday 0 (Monday) - stay on the same weekday, a week
    # later, so the new slot is actually free.
    new_start_at = start_at + dt.timedelta(days=7)

    resp = await client.post(
        f"/api/v1/bookings/{ctx['booking']['id']}/reschedule",
        headers=student["headers"],
        json={"new_start_at": new_start_at.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    tutor_events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "booking_rescheduled_by_student" in tutor_events

    ctx2 = await _setup_individual_booking(client, tutor, student)
    start_at2 = dt.datetime.fromisoformat(ctx2["booking"]["start_at"])
    # +14 (not +7, like above) so this reschedule target doesn't collide with the
    # first booking's already-rescheduled slot.
    new_start_at2 = start_at2 + dt.timedelta(days=14)
    resp = await client.post(
        f"/api/v1/bookings/{ctx2['booking']['id']}/reschedule",
        headers=tutor["headers"],
        json={"new_start_at": new_start_at2.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "booking_rescheduled_by_tutor" in student_events


async def test_group_application_lifecycle_notifications(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "sysnotif-tutor-group@example.com", "tutor")
    student = await _register(client, "sysnotif-student-group@example.com", "student")
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
        )
    ).json()["id"]
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Группа уведомлений",
            "lesson_type_id": lesson_type_id,
            "capacity": 3,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]

    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    assert app_resp.status_code == 201, app_resp.text
    tutor_events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "group_application_received" in tutor_events

    # В теле уведомления должна быть ссылка прямо на вкладку с заявками: иначе
    # репетитору приходится догадываться, где их рассматривать.
    application_notice = await _notification_body(
        db_session, tutor["user"]["id"], "group_application_received"
    )
    assert "/cabinet?tab=groups" in application_notice
    assert "Группа уведомлений" in application_notice

    accept_resp = await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
    )
    assert accept_resp.status_code == 200, accept_resp.text
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "group_application_accepted" in student_events

    leave_resp = await client.post(f"/api/v1/groups/{group_id}/leave", headers=student["headers"])
    assert leave_resp.status_code == 200, leave_resp.text
    tutor_events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "group_member_left" in tutor_events

    # Second application, this time rejected.
    app_resp2 = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    assert app_resp2.status_code == 201, app_resp2.text
    reject_resp = await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp2.json()['id']}/reject", headers=tutor["headers"]
    )
    assert reject_resp.status_code == 200, reject_resp.text
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "group_application_rejected" in student_events


async def test_group_occurrence_reschedule_notifies_active_members(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register(client, "sysnotif-tutor-occ@example.com", "tutor")
    student = await _register(client, "sysnotif-student-occ@example.com", "student")
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
        )
    ).json()["id"]
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Группа переносов",
            "lesson_type_id": lesson_type_id,
            "capacity": 3,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]
    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
    )

    occurrences = (await client.get(f"/api/v1/groups/{group_id}/occurrences", headers=tutor["headers"])).json()
    assert occurrences, "generate_occurrences should have created at least one upcoming session"
    occurrence = occurrences[0]
    new_start = dt.datetime.fromisoformat(occurrence["start_at"]) + dt.timedelta(hours=2)
    new_end = dt.datetime.fromisoformat(occurrence["end_at"]) + dt.timedelta(hours=2)

    resp = await client.patch(
        f"/api/v1/groups/{group_id}/occurrences/{occurrence['id']}",
        headers=tutor["headers"],
        json={"start_at": new_start.isoformat(), "end_at": new_end.isoformat()},
    )
    assert resp.status_code == 200, resp.text

    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "group_schedule_changed" in student_events


async def test_homework_assigned_notifies_student(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "sysnotif-tutor-hw@example.com", "tutor")
    student = await _register(client, "sysnotif-student-hw@example.com", "student")

    resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "Домашка №1",
            "submission_mode": "mark_done",
            "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/homework",
        },
    )
    assert resp.status_code == 201, resp.text
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "homework_assigned" in student_events


async def test_system_notifications_endpoints(client: AsyncClient, db_session: AsyncSession) -> None:
    student = await _register(client, "sysnotif-endpoints@example.com", "student")

    list_resp = await client.get("/api/v1/notifications/system", headers=student["headers"])
    assert list_resp.status_code == 200, list_resp.text
    notifications = list_resp.json()
    assert len(notifications) >= 1
    assert notifications[0]["read_at"] is None

    summary_resp = await client.get("/api/v1/notifications/unread-summary", headers=student["headers"])
    assert summary_resp.status_code == 200, summary_resp.text
    summary = summary_resp.json()
    assert summary["system_unread"] >= 1
    assert summary["total"] == summary["chat_unread"] + summary["system_unread"]

    mark_resp = await client.post("/api/v1/notifications/system/read", headers=student["headers"])
    assert mark_resp.status_code == 200, mark_resp.text

    summary_resp2 = await client.get("/api/v1/notifications/unread-summary", headers=student["headers"])
    assert summary_resp2.json()["system_unread"] == 0

    list_resp2 = await client.get("/api/v1/notifications/system", headers=student["headers"])
    assert all(n["read_at"] is not None for n in list_resp2.json())


async def test_admin_can_list_and_update_notification_templates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_headers = await _admin_headers(client, db_session)

    list_resp = await client.get("/api/v1/admin/notification-templates", headers=admin_headers)
    assert list_resp.status_code == 200, list_resp.text
    templates = list_resp.json()
    assert len(templates) > 0
    welcome_student = next(t for t in templates if t["event_type"] == "welcome" and t["role"] == "student")

    update_resp = await client.put(
        f"/api/v1/admin/notification-templates/{welcome_student['id']}",
        headers=admin_headers,
        json={"title": "Привет!", "body": "Рады видеть вас, {name}!"},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["title"] == "Привет!"

    student = await _register(client, "sysnotif-custom-template@example.com", "student")
    events_resp = await client.get("/api/v1/notifications/system", headers=student["headers"])
    welcome = next(n for n in events_resp.json() if n["event_type"] == "welcome")
    assert welcome["title"] == "Привет!"
    assert "Рады видеть вас" in welcome["body"]


async def test_non_admin_cannot_access_notification_templates(client: AsyncClient) -> None:
    student = await _register(client, "sysnotif-forbidden@example.com", "student")
    resp = await client.get("/api/v1/admin/notification-templates", headers=student["headers"])
    assert resp.status_code == 403


async def test_removed_student_is_notified(client: AsyncClient, db_session: AsyncSession) -> None:
    """Исключение из группы раньше проходило молча - занятия просто пропадали."""
    tutor = await _register(client, "sysnotif-remove-tutor@example.com", "tutor")
    student = await _register(client, "sysnotif-remove-student@example.com", "student")

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
                "name": "Группа исключения",
                "lesson_type_id": lesson_type_id,
                "capacity": 3,
                "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
            },
        )
    ).json()["id"]

    application = await client.post(
        f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={}
    )
    accept = await client.post(
        f"/api/v1/groups/{group_id}/applications/{application.json()['id']}/accept",
        headers=tutor["headers"],
    )
    assert accept.status_code == 200, accept.text

    student_id = student["user"]["id"]
    assert "group_member_removed" not in await _events_for_user(db_session, student_id)

    removal = await client.delete(
        f"/api/v1/groups/{group_id}/members/{student_id}", headers=tutor["headers"]
    )
    assert removal.status_code == 200, removal.text

    assert "group_member_removed" in await _events_for_user(db_session, student_id)
    body = await _notification_body(db_session, student_id, "group_member_removed")
    assert "Группа исключения" in body
