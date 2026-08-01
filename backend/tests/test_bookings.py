import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import RecurringSeries
from app.services import booking_service

MSK = ZoneInfo("Europe/Moscow")


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


def _next_weekday_datetime(weekday: int, hour: int, weeks_ahead: int = 2) -> dt.datetime:
    today = dt.date.today()
    days_ahead = (weekday - today.weekday()) % 7
    target_date = today + dt.timedelta(days=days_ahead + 7 * weeks_ahead)
    return dt.datetime.combine(target_date, dt.time(hour, 0), tzinfo=MSK)


async def _setup_tutor(client: AsyncClient, email: str, min_lead_time_hours: int = 1, **profile_overrides) -> dict:
    tutor = await _register(client, email, "tutor")
    patch = {"min_lead_time_hours": min_lead_time_hours, **profile_overrides}
    await client.patch("/api/v1/tutors/me", headers=tutor["headers"], json=patch)
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
    )
    assert lesson_type_resp.status_code == 201, lesson_type_resp.text
    tutor["lesson_type_id"] = lesson_type_resp.json()["id"]
    tutor["id"] = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    await client.put(
        "/api/v1/tutors/me/availability",
        headers=tutor["headers"],
        json={"intervals": [{"weekday": 0, "start_time": "09:00:00", "end_time": "20:00:00"}]},
    )
    return tutor


async def test_student_books_and_lists_lesson(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor1@example.com")
    student = await _register(client, "book-student1@example.com", "student")

    start_at = _next_weekday_datetime(0, 10)
    resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor["id"], "lesson_type_id": tutor["lesson_type_id"], "start_at": start_at.isoformat()},
    )
    assert resp.status_code == 201, resp.text
    booking = resp.json()
    assert booking["status"] == "scheduled"
    assert booking["booked_by"] == "student"
    # Student-facing responses carry the lesson type name and the tutor's "Имя
    # Отчество" (no surname) so booking cards don't need a separate lookup.
    assert booking["lesson_type_name"] == "Занятие"
    assert booking["tutor_display_name"] == "Test"

    student_list_resp = await client.get("/api/v1/bookings/me", headers=student["headers"])
    student_list = student_list_resp.json()
    assert len(student_list) == 1
    assert student_list[0]["lesson_type_name"] == "Занятие"
    assert student_list[0]["tutor_display_name"] == "Test"

    tutor_list = await client.get("/api/v1/bookings/tutor/me", headers=tutor["headers"])
    assert len(tutor_list.json()) == 1


async def test_booking_conflict_rejected(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor2@example.com")
    student = await _register(client, "book-student2@example.com", "student")

    start_at = _next_weekday_datetime(0, 10)
    payload = {
        "tutor_id": tutor["id"],
        "lesson_type_id": tutor["lesson_type_id"],
        "start_at": start_at.isoformat(),
    }
    first = await client.post("/api/v1/bookings", headers=student["headers"], json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/bookings", headers=student["headers"], json=payload)
    assert second.status_code == 409


async def test_cancel_respects_min_hours_before(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor3@example.com", cancel_min_hours_before=48)
    student = await _register(client, "book-student3@example.com", "student")

    # Manual tutor bookings skip the weekly-availability grid entirely, so this is a
    # deterministic way to get a booking "soon" (well inside the 48h cancel deadline)
    # regardless of what weekday/time the test happens to run at.
    start_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5)
    end_at = start_at + dt.timedelta(hours=1)
    create_resp = await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={
            "student_id": student["user"]["id"],
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    booking_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/cancel", headers=student["headers"], json={"reason": "test"}
    )
    assert cancel_resp.status_code == 409


async def test_cancel_monthly_limit(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor4@example.com", cancel_min_hours_before=1, cancel_max_per_month=1)
    student = await _register(client, "book-student4@example.com", "student")

    slot1 = _next_weekday_datetime(0, 10, weeks_ahead=2)
    slot2 = _next_weekday_datetime(0, 12, weeks_ahead=2)

    b1 = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor["id"], "lesson_type_id": tutor["lesson_type_id"], "start_at": slot1.isoformat()},
    )
    b2 = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor["id"], "lesson_type_id": tutor["lesson_type_id"], "start_at": slot2.isoformat()},
    )
    assert b1.status_code == 201 and b2.status_code == 201

    cancel1 = await client.post(f"/api/v1/bookings/{b1.json()['id']}/cancel", headers=student["headers"], json={})
    assert cancel1.status_code == 200

    cancel2 = await client.post(f"/api/v1/bookings/{b2.json()['id']}/cancel", headers=student["headers"], json={})
    assert cancel2.status_code == 409


async def test_reschedule_creates_new_booking_and_closes_old(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor5@example.com", reschedule_min_hours_before=1)
    student = await _register(client, "book-student5@example.com", "student")

    original_start = _next_weekday_datetime(0, 10)
    create_resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor["id"], "lesson_type_id": tutor["lesson_type_id"], "start_at": original_start.isoformat()},
    )
    booking_id = create_resp.json()["id"]

    new_start = _next_weekday_datetime(0, 15)
    resched_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/reschedule",
        headers=student["headers"],
        json={"new_start_at": new_start.isoformat()},
    )
    assert resched_resp.status_code == 200, resched_resp.text
    new_booking = resched_resp.json()
    assert new_booking["rescheduled_from_id"] == booking_id
    assert new_booking["status"] == "scheduled"

    student_list = (await client.get("/api/v1/bookings/me", headers=student["headers"])).json()
    by_id = {b["id"]: b for b in student_list}
    assert by_id[booking_id]["status"] == "rescheduled"
    assert by_id[new_booking["id"]]["status"] == "scheduled"


async def test_reschedule_availability_excludes_own_booking_and_rejects_other_students(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor5b@example.com", reschedule_min_hours_before=1)
    student = await _register(client, "book-student5b@example.com", "student")
    outsider = await _register(client, "book-student5c@example.com", "student")

    booked_start = _next_weekday_datetime(0, 10)
    create_resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor["id"], "lesson_type_id": tutor["lesson_type_id"], "start_at": booked_start.isoformat()},
    )
    booking_id = create_resp.json()["id"]

    target_date = booked_start.date().isoformat()

    # The booking's own slot must show up as available for rescheduling (it would
    # otherwise conflict with itself under the normal booking-availability check).
    dates_resp = await client.get(
        f"/api/v1/bookings/{booking_id}/reschedule/dates",
        headers=student["headers"],
        params={"date_from": target_date, "date_to": target_date},
    )
    assert dates_resp.status_code == 200, dates_resp.text
    assert target_date in dates_resp.json()

    slots_resp = await client.get(
        f"/api/v1/bookings/{booking_id}/reschedule/slots",
        headers=student["headers"],
        params={"date": target_date},
    )
    assert slots_resp.status_code == 200, slots_resp.text
    own_slot = next(s for s in slots_resp.json() if s["start_at"] == booked_start.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"))
    assert own_slot["available"] is True

    # A student who doesn't own the booking cannot browse its reschedule availability.
    forbidden = await client.get(
        f"/api/v1/bookings/{booking_id}/reschedule/slots",
        headers=outsider["headers"],
        params={"date": target_date},
    )
    assert forbidden.status_code == 403


async def test_recurring_series_generates_future_occurrences_and_can_be_stopped(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _setup_tutor(client, "book-tutor6@example.com")
    student = await _register(client, "book-student6@example.com", "student")

    start_at = _next_weekday_datetime(0, 10)
    resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={
            "tutor_id": tutor["id"],
            "lesson_type_id": tutor["lesson_type_id"],
            "start_at": start_at.isoformat(),
            "repeat_weekly": True,
        },
    )
    assert resp.status_code == 201, resp.text
    series_id = resp.json()["recurring_series_id"]
    assert series_id is not None

    student_list = (await client.get("/api/v1/bookings/me", headers=student["headers"])).json()
    series_bookings = [b for b in student_list if b["recurring_series_id"] == series_id]
    # The originally requested booking plus RECURRING_WEEKS_AHEAD generated ones.
    assert len(series_bookings) == 1 + booking_service.RECURRING_WEEKS_AHEAD

    stop_resp = await client.post(f"/api/v1/bookings/series/{series_id}/stop", headers=student["headers"])
    assert stop_resp.status_code == 200
    assert stop_resp.json()["is_active"] is False

    result = await db_session.execute(select(RecurringSeries).where(RecurringSeries.id == uuid.UUID(series_id)))
    series = result.scalar_one()
    further = await booking_service.generate_recurring_occurrences(
        db_session, series, initiated_by="student", anchor_date=dt.date.today()
    )
    assert further == []


async def test_list_my_recurring_series_shows_enriched_details_and_drops_stopped(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor6b@example.com")
    student = await _register(client, "book-student6b@example.com", "student")

    start_at = _next_weekday_datetime(0, 9)
    resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={
            "tutor_id": tutor["id"],
            "lesson_type_id": tutor["lesson_type_id"],
            "start_at": start_at.isoformat(),
            "repeat_weekly": True,
        },
    )
    series_id = resp.json()["recurring_series_id"]

    list_resp = await client.get("/api/v1/bookings/series/me", headers=student["headers"])
    assert list_resp.status_code == 200, list_resp.text
    series_list = list_resp.json()
    assert len(series_list) == 1
    assert series_list[0]["id"] == series_id
    assert series_list[0]["weekday"] == 0
    assert series_list[0]["lesson_type_name"] == "Занятие"
    assert series_list[0]["tutor_display_name"] == tutor["user"]["display_name"]

    await client.post(f"/api/v1/bookings/series/{series_id}/stop", headers=student["headers"])
    after_stop = (await client.get("/api/v1/bookings/series/me", headers=student["headers"])).json()
    assert after_stop == []


async def test_tutor_manual_block_and_crud(client: AsyncClient) -> None:
    tutor = await _setup_tutor(client, "book-tutor7@example.com")
    student = await _register(client, "book-student7@example.com", "student")

    start_at = _next_weekday_datetime(0, 10)
    end_at = start_at + dt.timedelta(hours=1)
    block_resp = await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={"start_at": start_at.isoformat(), "end_at": end_at.isoformat(), "notes": "личное дело"},
    )
    assert block_resp.status_code == 201, block_resp.text
    block = block_resp.json()
    assert block["is_manual_block"] is True
    assert block["student_id"] is None

    # A conflicting manual block should be rejected.
    conflict_resp = await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={"start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
    )
    assert conflict_resp.status_code == 409

    # Tutor attaches a student to the reserve via PATCH.
    patch_resp = await client.patch(
        f"/api/v1/bookings/{block['id']}",
        headers=tutor["headers"],
        json={"student_id": student["user"]["id"]},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["is_manual_block"] is False
    assert patch_resp.json()["student_id"] == student["user"]["id"]

    delete_resp = await client.delete(f"/api/v1/bookings/{block['id']}", headers=tutor["headers"])
    assert delete_resp.status_code == 204

    tutor_list = (await client.get("/api/v1/bookings/tutor/me", headers=tutor["headers"])).json()
    assert all(b["id"] != block["id"] for b in tutor_list)


async def test_tutor_can_cancel_and_reschedule_without_policy_limits(client: AsyncClient) -> None:
    # High policy thresholds that would block a student outright - a tutor managing
    # their own schedule isn't subject to them.
    tutor = await _setup_tutor(
        client,
        "book-tutor8@example.com",
        cancel_min_hours_before=48,
        reschedule_min_hours_before=48,
    )
    student = await _register(client, "book-student8@example.com", "student")

    start_at = _next_weekday_datetime(0, 10)
    create_resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor["id"], "lesson_type_id": tutor["lesson_type_id"], "start_at": start_at.isoformat()},
    )
    assert create_resp.status_code == 201, create_resp.text
    booking_id = create_resp.json()["id"]

    new_start = _next_weekday_datetime(0, 15)
    resched_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/reschedule",
        headers=tutor["headers"],
        json={"new_start_at": new_start.isoformat()},
    )
    assert resched_resp.status_code == 200, resched_resp.text
    new_booking = resched_resp.json()
    assert new_booking["status"] == "scheduled"
    assert new_booking["student_display_name"] is not None  # tutor-facing shape, not student-facing

    tutor_list = (await client.get("/api/v1/bookings/tutor/me", headers=tutor["headers"])).json()
    by_id = {b["id"]: b for b in tutor_list}
    assert by_id[booking_id]["status"] == "rescheduled"
    assert by_id[booking_id]["cancelled_by"] == "tutor"

    cancel_resp = await client.post(
        f"/api/v1/bookings/{new_booking['id']}/cancel", headers=tutor["headers"], json={"reason": None}
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelled_by_tutor"


async def test_tutor_cannot_cancel_or_reschedule_other_tutors_booking(client: AsyncClient) -> None:
    tutor_a = await _setup_tutor(client, "book-tutorC@example.com")
    tutor_b = await _setup_tutor(client, "book-tutorD@example.com")
    student = await _register(client, "book-student9@example.com", "student")

    start_at = _next_weekday_datetime(0, 10)
    create_resp = await client.post(
        "/api/v1/bookings",
        headers=student["headers"],
        json={"tutor_id": tutor_a["id"], "lesson_type_id": tutor_a["lesson_type_id"], "start_at": start_at.isoformat()},
    )
    booking_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/cancel", headers=tutor_b["headers"], json={"reason": None}
    )
    assert cancel_resp.status_code == 403

    reschedule_resp = await client.post(
        f"/api/v1/bookings/{booking_id}/reschedule",
        headers=tutor_b["headers"],
        json={"new_start_at": (start_at + dt.timedelta(hours=2)).isoformat()},
    )
    assert reschedule_resp.status_code == 403


async def test_tutor_cannot_modify_other_tutors_booking(client: AsyncClient) -> None:
    tutor_a = await _setup_tutor(client, "book-tutorA@example.com")
    tutor_b = await _setup_tutor(client, "book-tutorB@example.com")

    start_at = _next_weekday_datetime(0, 10)
    end_at = start_at + dt.timedelta(hours=1)
    block_resp = await client.post(
        "/api/v1/bookings/manual",
        headers=tutor_a["headers"],
        json={"start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
    )
    booking_id = block_resp.json()["id"]

    resp = await client.delete(f"/api/v1/bookings/{booking_id}", headers=tutor_b["headers"])
    assert resp.status_code == 403
