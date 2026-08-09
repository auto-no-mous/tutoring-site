import datetime as dt
import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus
from app.models.notification import NotificationLog
from app.models.system_notification import SystemNotification
from app.services.notification_service import send_upcoming_reminders


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


async def _events_for_user(db_session: AsyncSession, user_id: str) -> list[str]:
    result = await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == uuid.UUID(user_id))
    )
    return [log.event_type for log in result.scalars().all()]


async def test_new_booking_notifies_tutor(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "notif-tutor1@example.com", "tutor")
    student = await _register(client, "notif-student1@example.com", "student")
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
    # Land on a Monday within the wide-open availability window set above.
    days_to_monday = (0 - start_at.weekday()) % 7
    start_at = (start_at + dt.timedelta(days=days_to_monday)).replace(hour=10, minute=0, second=0, microsecond=0)

    resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor_id, "lesson_type_id": lesson_type_id, "start_at": start_at.isoformat()},
    )
    assert resp.status_code == 201, resp.text

    events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "new_booking" in events


async def test_group_application_and_withdrawal_notify_tutor(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "notif-tutor2@example.com", "tutor")
    student = await _register(client, "notif-student2@example.com", "student")
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
    )
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Группа уведомлений",
            "lesson_type_id": lesson_type_resp.json()["id"],
            "capacity": 3,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]

    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
    )
    await client.post(f"/api/v1/groups/{group_id}/leave", headers=student["headers"])

    events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "group_application" in events
    assert "group_withdrawal" in events


async def test_chat_message_notifies_tutor_only_when_sent_by_student(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register(client, "notif-tutor3@example.com", "tutor")
    student = await _register(client, "notif-student3@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    thread_id = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student["headers"])
    ).json()["id"]

    await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], data={"content": "Привет"}
    )
    tutor_events = await _events_for_user(db_session, tutor["user"]["id"])
    assert tutor_events.count("new_message") == 1

    await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=tutor["headers"], data={"content": "Здравствуйте"}
    )
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "new_message" not in student_events  # notifications are tutor-facing only (section 2.7)


async def test_upcoming_reminder_sent_once(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "notif-tutor4@example.com", "tutor")
    student = await _register(client, "notif-student4@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]

    # Both tutor and student default to a 60-minute reminder lead time (see
    # User.reminder_lead_minutes / Settings) - land the booking right at that mark so
    # both are due at once.
    start_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=60)
    booking = Booking(
        tutor_id=uuid.UUID(tutor_id),
        student_id=uuid.UUID(student["user"]["id"]),
        lesson_type_id=uuid.UUID(lesson_type_id),
        start_at=start_at,
        end_at=start_at + dt.timedelta(hours=1),
        status=BookingStatus.SCHEDULED.value,
    )
    db_session.add(booking)
    await db_session.commit()

    # Tutor and student are reminded independently - both fire on the same run here
    # since both use the default lead time.
    sent_count = await send_upcoming_reminders(db_session)
    assert sent_count == 2

    tutor_events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "upcoming_reminder" in tutor_events
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "upcoming_reminder" in student_events

    # Running again shouldn't re-notify the same booking for either recipient.
    sent_again = await send_upcoming_reminders(db_session)
    assert sent_again == 0


async def test_reminder_lead_time_is_per_user_and_independent(client: AsyncClient, db_session: AsyncSession) -> None:
    """Tutor and student can configure different lead times (Settings, next to the
    Telegram connect button) - each is reminded on their own schedule, not the
    other's."""
    tutor = await _register(client, "notif-tutor5@example.com", "tutor")
    student = await _register(client, "notif-student5@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]

    # Student wants an earlier heads-up (15 min); tutor keeps the 60-minute default.
    settings_resp = await client.patch(
        "/api/v1/auth/me", headers=student["headers"], json={"reminder_lead_minutes": 15}
    )
    assert settings_resp.status_code == 200, settings_resp.text
    assert settings_resp.json()["reminder_lead_minutes"] == 15

    start_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)
    booking = Booking(
        tutor_id=uuid.UUID(tutor_id),
        student_id=uuid.UUID(student["user"]["id"]),
        lesson_type_id=uuid.UUID(lesson_type_id),
        start_at=start_at,
        end_at=start_at + dt.timedelta(hours=1),
        status=BookingStatus.SCHEDULED.value,
    )
    db_session.add(booking)
    await db_session.commit()

    # At the 15-minute mark, only the student (lead=15) is due - the tutor (lead=60)
    # isn't due for another 45 minutes.
    sent_count = await send_upcoming_reminders(db_session)
    assert sent_count == 1
    student_events = await _events_for_user(db_session, student["user"]["id"])
    assert "upcoming_reminder" in student_events
    tutor_events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "upcoming_reminder" not in tutor_events

    # The in-app "Системные уведомления" copy names the actual configured lead time.
    sysnotif_result = await db_session.execute(
        select(SystemNotification).where(SystemNotification.user_id == uuid.UUID(student["user"]["id"]))
    )
    reminder = next(
        r for r in sysnotif_result.scalars().all() if r.event_type == "upcoming_lesson_reminder"
    )
    assert "15" in reminder.body
    assert tutor["user"]["display_name"] in reminder.body


async def test_reminder_lead_minutes_bounds_validated(client: AsyncClient) -> None:
    student = await _register(client, "notif-student6@example.com", "student")

    too_low = await client.patch("/api/v1/auth/me", headers=student["headers"], json={"reminder_lead_minutes": 0})
    assert too_low.status_code == 422

    too_high = await client.patch(
        "/api/v1/auth/me", headers=student["headers"], json={"reminder_lead_minutes": 7 * 24 * 60 + 1}
    )
    assert too_high.status_code == 422

    default_resp = await client.get("/api/v1/auth/me", headers=student["headers"])
    assert default_resp.json()["reminder_lead_minutes"] == 60
