import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus

MSK = ZoneInfo("Europe/Moscow")


def _next_weekday(weekday: int, weeks_ahead: int = 2) -> dt.date:
    today = dt.date.today()
    days_ahead = (weekday - today.weekday()) % 7
    return today + dt.timedelta(days=days_ahead + 7 * weeks_ahead)


def _slots_by_start(payload: list[dict]) -> dict[dt.datetime, bool]:
    return {
        dt.datetime.fromisoformat(s["start_at"].replace("Z", "+00:00")): s["available"] for s in payload
    }


async def _register_tutor(client: AsyncClient, email: str = "tutor@example.com") -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret1",
            "first_name": "Тестовый",
            "last_name": "Репетитор",
            "role": "tutor",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    token = body["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return {"headers": headers, "user": body["user"]}


async def test_tutor_profile_created_on_registration(client: AsyncClient) -> None:
    tutor = await _register_tutor(client)
    resp = await client.get("/api/v1/tutors/me", headers=tutor["headers"])
    assert resp.status_code == 200, resp.text
    profile = resp.json()
    assert profile["slot_granularity_minutes"] == 15
    assert profile["min_lead_time_hours"] == 24
    assert profile["is_hidden"] is False


async def test_update_profile_and_hide_from_catalog(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "hidden-tutor@example.com")
    resp = await client.patch(
        "/api/v1/tutors/me",
        headers=tutor["headers"],
        json={"about": "10 лет опыта", "is_hidden": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_hidden"] is True
    tutor_id = resp.json()["id"]

    # Hidden profiles are excluded from the public catalog...
    catalog_resp = await client.get("/api/v1/tutors")
    assert all(item["id"] != tutor_id for item in catalog_resp.json())

    # ...but remain reachable by direct link.
    direct_resp = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert direct_resp.status_code == 200
    assert direct_resp.json()["about"] == "10 лет опыта"


async def test_lesson_type_duration_must_match_granularity(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "granularity@example.com")
    resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Индивидуальное занятие", "format": "individual", "duration_minutes": 50, "price": 1500},
    )
    assert resp.status_code == 422, resp.text


async def test_catalog_price_filter_and_public_lesson_types(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "catalog-tutor@example.com")
    create_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 2000},
    )
    assert create_resp.status_code == 201, create_resp.text

    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    in_range = await client.get("/api/v1/tutors", params={"price_min": 1000, "price_max": 3000})
    assert any(item["id"] == tutor_id for item in in_range.json())

    out_of_range = await client.get("/api/v1/tutors", params={"price_min": 5000})
    assert all(item["id"] != tutor_id for item in out_of_range.json())

    public_types = await client.get(f"/api/v1/tutors/{tutor_id}/lesson-types")
    assert public_types.status_code == 200
    assert len(public_types.json()) == 1
    assert public_types.json()[0]["price"] == 2000


async def test_slot_computation_respects_break_and_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register_tutor(client, "slots-tutor@example.com")
    await client.patch(
        "/api/v1/tutors/me",
        headers=tutor["headers"],
        json={"break_between_lessons_minutes": 15, "min_lead_time_hours": 1},
    )
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
    )
    lesson_type_id = lesson_type_resp.json()["id"]
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    target_date = _next_weekday(weekday=0)  # a Monday, well beyond the 1h lead time
    availability_resp = await client.put(
        "/api/v1/tutors/me/availability",
        headers=tutor["headers"],
        json={"intervals": [{"weekday": 0, "start_time": "09:00:00", "end_time": "14:00:00"}]},
    )
    assert availability_resp.status_code == 200, availability_resp.text

    # No bookings yet: 09:00 should be available.
    slots_resp = await client.get(
        f"/api/v1/tutors/{tutor_id}/availability/slots",
        params={"lesson_type_id": lesson_type_id, "date": target_date.isoformat()},
    )
    assert slots_resp.status_code == 200, slots_resp.text
    slots = _slots_by_start(slots_resp.json())
    nine_am_utc = dt.datetime.combine(target_date, dt.time(9, 0), tzinfo=MSK).astimezone(dt.timezone.utc)
    assert slots[nine_am_utc] is True

    # Directly insert a booking 09:00-10:00 to simulate an existing reservation (booking
    # creation endpoint is a separate task) and confirm the documented example from
    # project_description.md section 2.3: 09:00/09:15/09:30/09:45/10:00 become blocked,
    # 10:15 is the first free slot again.
    ten_am_utc = nine_am_utc + dt.timedelta(hours=1)
    db_session.add(
        Booking(
            tutor_id=uuid.UUID(tutor_id),
            student_id=None,
            lesson_type_id=uuid.UUID(lesson_type_id),
            start_at=nine_am_utc,
            end_at=ten_am_utc,
            status=BookingStatus.SCHEDULED.value,
            is_manual_block=True,
        )
    )
    await db_session.commit()

    slots_resp = await client.get(
        f"/api/v1/tutors/{tutor_id}/availability/slots",
        params={"lesson_type_id": lesson_type_id, "date": target_date.isoformat()},
    )
    slots = _slots_by_start(slots_resp.json())

    for minute_offset in (0, 15, 30, 45, 60):
        blocked_start = nine_am_utc + dt.timedelta(minutes=minute_offset)
        assert slots[blocked_start] is False, f"{blocked_start} should be blocked"

    free_again = nine_am_utc + dt.timedelta(minutes=75)  # 10:15
    assert slots[free_again] is True


async def test_available_dates_skip_days_without_capacity(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "dates-tutor@example.com")
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
    )
    lesson_type_id = lesson_type_resp.json()["id"]
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    # Only Wednesdays are available.
    await client.put(
        "/api/v1/tutors/me/availability",
        headers=tutor["headers"],
        json={"intervals": [{"weekday": 2, "start_time": "10:00:00", "end_time": "11:00:00"}]},
    )

    date_from = dt.date.today() + dt.timedelta(days=1)
    date_to = date_from + dt.timedelta(days=13)
    resp = await client.get(
        f"/api/v1/tutors/{tutor_id}/availability/dates",
        params={
            "lesson_type_id": lesson_type_id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
    )
    assert resp.status_code == 200, resp.text
    returned_dates = [dt.date.fromisoformat(d) for d in resp.json()]
    assert all(d.weekday() == 2 for d in returned_dates)
    assert len(returned_dates) == 2  # two Wednesdays in a 14-day window
