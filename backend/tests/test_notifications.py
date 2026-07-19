import datetime as dt
import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus
from app.models.notification import NotificationLog
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

    start_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)
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

    sent_count = await send_upcoming_reminders(db_session)
    assert sent_count == 1

    events = await _events_for_user(db_session, tutor["user"]["id"])
    assert "upcoming_reminder" in events

    # Running again shouldn't re-notify the same booking.
    sent_again = await send_upcoming_reminders(db_session)
    assert sent_again == 0
