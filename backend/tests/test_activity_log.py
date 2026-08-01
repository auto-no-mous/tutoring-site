import datetime as dt
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus, GroupMembershipStatus, GroupOccurrenceStatus
from app.models.group import GroupMembership, GroupOccurrence


async def _register(client: AsyncClient, email: str, role: str) -> dict:
    return await _register_named(client, email, role, "Test", role)


async def _register_named(client: AsyncClient, email: str, role: str, first_name: str, last_name: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret1",
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}
    return {"headers": headers, "user": body["user"]}


async def _insert_past_booking(
    db_session: AsyncSession, tutor_id: str, student_id: str, lesson_type_id: str, hours_ago: int
) -> uuid.UUID:
    end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_ago)
    start = end - dt.timedelta(hours=1)
    booking = Booking(
        tutor_id=uuid.UUID(tutor_id),
        student_id=uuid.UUID(student_id),
        lesson_type_id=uuid.UUID(lesson_type_id),
        start_at=start,
        end_at=end,
        status=BookingStatus.SCHEDULED.value,
    )
    db_session.add(booking)
    await db_session.commit()
    await db_session.refresh(booking)
    return booking.id


async def _setup_tutor_with_group(client: AsyncClient, email: str, capacity: int = 3) -> dict:
    tutor = await _register(client, email, "tutor")
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа подготовки", "format": "group", "duration_minutes": 90, "price": 500},
    )
    lesson_type_id = lesson_type_resp.json()["id"]
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Подготовка к ЕГЭ",
            "lesson_type_id": lesson_type_id,
            "capacity": capacity,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    assert group_resp.status_code == 201, group_resp.text
    tutor["group"] = group_resp.json()
    return tutor


async def _insert_past_occurrence(
    db_session: AsyncSession, group_id: str, hours_ago: int
) -> uuid.UUID:
    end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_ago)
    start = end - dt.timedelta(hours=1, minutes=30)
    occurrence = GroupOccurrence(
        group_id=uuid.UUID(group_id), start_at=start, end_at=end, status=GroupOccurrenceStatus.SCHEDULED.value
    )
    db_session.add(occurrence)
    await db_session.commit()
    await db_session.refresh(occurrence)
    return occurrence.id


async def _add_member(db_session: AsyncSession, group_id: str, student_id: str, joined_hours_ago: int) -> None:
    db_session.add(
        GroupMembership(
            group_id=uuid.UUID(group_id),
            student_id=uuid.UUID(student_id),
            status=GroupMembershipStatus.ACTIVE.value,
            joined_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=joined_hours_ago),
        )
    )
    await db_session.commit()


async def test_booking_outcome_default_and_override(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "log-tutor1@example.com", "tutor")
    student = await _register(client, "log-student1@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]
    booking_id = await _insert_past_booking(db_session, tutor_id, student["user"]["id"], lesson_type_id, hours_ago=2)

    # Default (unset) outcome shows as "conducted" in both logs without any write.
    tutor_log = (await client.get("/api/v1/stats/tutor/me/log", headers=tutor["headers"])).json()
    assert tutor_log["total"] == 1
    assert tutor_log["entries"][0]["event_type"] == "lesson_conducted"
    assert tutor_log["entries"][0]["status_label"] == "Проведено успешно"
    assert tutor_log["entries"][0]["counterpart_name"] == "student Test"  # last_name first_name

    student_log = (await client.get("/api/v1/stats/student/me/log", headers=student["headers"])).json()
    assert student_log["entries"][0]["event_type"] == "lesson_conducted"

    # Tutor overrides to student_no_show.
    patch_resp = await client.patch(
        f"/api/v1/bookings/{booking_id}/outcome", headers=tutor["headers"], json={"outcome": "student_no_show"}
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["outcome"] == "student_no_show"

    tutor_log2 = (await client.get("/api/v1/stats/tutor/me/log", headers=tutor["headers"])).json()
    assert tutor_log2["entries"][0]["event_type"] == "lesson_student_no_show"
    assert tutor_log2["entries"][0]["status_label"] == "Ученик не явился"

    # Student can't set outcomes, and a future booking can't have one recorded.
    denied = await client.patch(
        f"/api/v1/bookings/{booking_id}/outcome", headers=student["headers"], json={"outcome": "conducted"}
    )
    assert denied.status_code == 403


async def test_booking_outcome_rejects_future_and_cancelled(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "log-tutor2@example.com", "tutor")
    student = await _register(client, "log-student2@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]

    future_booking_id = await _insert_past_booking(
        db_session, tutor_id, student["user"]["id"], lesson_type_id, hours_ago=-48
    )
    not_happened_yet = await client.patch(
        f"/api/v1/bookings/{future_booking_id}/outcome", headers=tutor["headers"], json={"outcome": "conducted"}
    )
    assert not_happened_yet.status_code == 409

    cancel_resp = await client.post(
        f"/api/v1/bookings/{future_booking_id}/cancel", headers=student["headers"], json={"reason": None}
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    wrong_status = await client.patch(
        f"/api/v1/bookings/{future_booking_id}/outcome", headers=tutor["headers"], json={"outcome": "conducted"}
    )
    assert wrong_status.status_code == 409


async def test_group_attendance_per_student(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _setup_tutor_with_group(client, "log-tutor3@example.com", capacity=5)
    group_id = tutor["group"]["id"]
    student1 = await _register_named(client, "log-student3a@example.com", "student", "Anna", "Ivanova")
    student2 = await _register_named(client, "log-student3b@example.com", "student", "Boris", "Petrov")

    occurrence_id = await _insert_past_occurrence(db_session, group_id, hours_ago=3)
    await _add_member(db_session, group_id, student1["user"]["id"], joined_hours_ago=10)
    await _add_member(db_session, group_id, student2["user"]["id"], joined_hours_ago=10)

    # Default: both conducted.
    default_attendance = (
        await client.get(f"/api/v1/groups/{group_id}/occurrences/{occurrence_id}/attendance", headers=tutor["headers"])
    ).json()
    assert len(default_attendance) == 2
    assert {a["outcome"] for a in default_attendance} == {"conducted"}

    # Mark student1 absent, student2 conducted.
    put_resp = await client.put(
        f"/api/v1/groups/{group_id}/occurrences/{occurrence_id}/attendance",
        headers=tutor["headers"],
        json={
            "entries": [
                {"student_id": student1["user"]["id"], "outcome": "student_no_show"},
                {"student_id": student2["user"]["id"], "outcome": "conducted"},
            ]
        },
    )
    assert put_resp.status_code == 200, put_resp.text

    tutor_log = (await client.get("/api/v1/stats/tutor/me/log", headers=tutor["headers"])).json()
    outcomes = {e["counterpart_name"]: e["event_type"] for e in tutor_log["entries"]}
    assert outcomes["Ivanova Anna"] == "group_lesson_student_no_show"
    assert outcomes["Petrov Boris"] == "group_lesson_conducted"

    student1_log = (await client.get("/api/v1/stats/student/me/log", headers=student1["headers"])).json()
    assert student1_log["entries"][0]["event_type"] == "group_lesson_student_no_show"

    student2_log = (await client.get("/api/v1/stats/student/me/log", headers=student2["headers"])).json()
    assert student2_log["entries"][0]["event_type"] == "group_lesson_conducted"


async def test_group_application_and_membership_log_entries(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "log-tutor4@example.com", capacity=2)
    group_id = tutor["group"]["id"]
    student1 = await _register(client, "log-student4a@example.com", "student")
    student2 = await _register(client, "log-student4b@example.com", "student")

    app1 = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student1["headers"], json={})
    app2 = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student2["headers"], json={})
    await client.post(f"/api/v1/groups/{group_id}/applications/{app1.json()['id']}/accept", headers=tutor["headers"])
    await client.post(f"/api/v1/groups/{group_id}/applications/{app2.json()['id']}/accept", headers=tutor["headers"])

    await client.post(f"/api/v1/groups/{group_id}/leave", headers=student1["headers"])
    await client.delete(f"/api/v1/groups/{group_id}/members/{student2['user']['id']}", headers=tutor["headers"])

    tutor_log = (await client.get("/api/v1/stats/tutor/me/log", headers=tutor["headers"])).json()
    event_types = {e["event_type"] for e in tutor_log["entries"]}
    assert "group_application_accepted" in event_types
    assert "group_membership_left" in event_types
    assert "group_membership_removed" in event_types

    student1_log = (await client.get("/api/v1/stats/student/me/log", headers=student1["headers"])).json()
    student1_types = {e["event_type"] for e in student1_log["entries"]}
    assert "group_membership_left" in student1_types
    assert "group_membership_removed" not in student1_types


async def test_activity_log_event_type_filter_and_pagination(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "log-tutor5@example.com", "tutor")
    student = await _register(client, "log-student5@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]

    for i in range(3):
        booking_id = await _insert_past_booking(
            db_session, tutor_id, student["user"]["id"], lesson_type_id, hours_ago=2 + i
        )
        if i == 0:
            await client.patch(
                f"/api/v1/bookings/{booking_id}/outcome", headers=tutor["headers"], json={"outcome": "student_no_show"}
            )

    all_log = (await client.get("/api/v1/stats/tutor/me/log", headers=tutor["headers"])).json()
    assert all_log["total"] == 3

    filtered = (
        await client.get(
            "/api/v1/stats/tutor/me/log",
            headers=tutor["headers"],
            params={"event_types": ["lesson_student_no_show"]},
        )
    ).json()
    assert filtered["total"] == 1
    assert filtered["entries"][0]["event_type"] == "lesson_student_no_show"

    page1 = (
        await client.get("/api/v1/stats/tutor/me/log", headers=tutor["headers"], params={"page": 1, "page_size": 2})
    ).json()
    assert len(page1["entries"]) == 2
    assert page1["total"] == 3

    page2 = (
        await client.get("/api/v1/stats/tutor/me/log", headers=tutor["headers"], params={"page": 2, "page_size": 2})
    ).json()
    assert len(page2["entries"]) == 1

    page1_ids = {e["id"] for e in page1["entries"]}
    page2_ids = {e["id"] for e in page2["entries"]}
    assert page1_ids.isdisjoint(page2_ids)
