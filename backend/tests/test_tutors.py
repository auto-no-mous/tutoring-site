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
    assert all(item["id"] != tutor_id for item in catalog_resp.json()["items"])

    # ...but remain reachable by direct link.
    direct_resp = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert direct_resp.status_code == 200
    assert direct_resp.json()["about"] == "10 лет опыта"


async def test_about_field_sanitized_server_side(client: AsyncClient) -> None:
    """Regression test: 'about' used to be trusted verbatim from the client, relying
    entirely on the frontend editor to sanitize before ever saving it - a direct API
    call (bypassing the editor) could store a script/event-handler payload that would
    later execute wherever 'about' gets rendered (e.g. an admin editing that tutor).
    See app.utils.html_sanitize."""
    tutor = await _register_tutor(client, "xss-about-tutor@example.com")
    payload = '<img src="x" onerror="alert(1)"><script>evil()</script><p>Опытный репетитор</p>'
    resp = await client.patch("/api/v1/tutors/me", headers=tutor["headers"], json={"about": payload})
    assert resp.status_code == 200, resp.text
    saved_about = resp.json()["about"]
    assert "onerror" not in saved_about
    assert "<script" not in saved_about
    assert "Опытный репетитор" in saved_about


async def test_tutor_slug_set_and_resolve(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "slug-tutor@example.com")

    set_resp = await client.patch("/api/v1/tutors/me", headers=tutor["headers"], json={"slug": "smoke-tutor"})
    assert set_resp.status_code == 200, set_resp.text
    assert set_resp.json()["slug"] == "smoke-tutor"
    tutor_id = set_resp.json()["id"]

    by_slug = await client.get("/api/v1/tutors/smoke-tutor")
    assert by_slug.status_code == 200
    assert by_slug.json()["id"] == tutor_id

    by_id = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert by_id.status_code == 200
    assert by_id.json()["id"] == tutor_id

    missing = await client.get("/api/v1/tutors/no-such-slug")
    assert missing.status_code == 404


async def test_tutor_slug_uniqueness_and_reserved_word(client: AsyncClient) -> None:
    tutor_a = await _register_tutor(client, "slug-a@example.com")
    tutor_b = await _register_tutor(client, "slug-b@example.com")

    first = await client.patch("/api/v1/tutors/me", headers=tutor_a["headers"], json={"slug": "taken-nick"})
    assert first.status_code == 200, first.text

    dup = await client.patch("/api/v1/tutors/me", headers=tutor_b["headers"], json={"slug": "taken-nick"})
    assert dup.status_code == 409

    # Re-setting your own current slug to itself is not a conflict.
    same = await client.patch("/api/v1/tutors/me", headers=tutor_a["headers"], json={"slug": "taken-nick"})
    assert same.status_code == 200

    reserved = await client.patch("/api/v1/tutors/me", headers=tutor_b["headers"], json={"slug": "me"})
    assert reserved.status_code == 422

    bad_format = await client.patch("/api/v1/tutors/me", headers=tutor_b["headers"], json={"slug": "Not Valid!"})
    assert bad_format.status_code == 422

    # Clearing the slug (explicit null) goes back to no nickname.
    cleared = await client.patch("/api/v1/tutors/me", headers=tutor_a["headers"], json={"slug": None})
    assert cleared.status_code == 200
    assert cleared.json()["slug"] is None


async def test_tutor_social_links_saved_and_shown_on_public_profile(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "social-tutor@example.com")
    resp = await client.patch(
        "/api/v1/tutors/me",
        headers=tutor["headers"],
        json={
            "telegram_url": "https://t.me/example",
            "vk_url": "https://vk.com/example",
            "youtube_url": "https://youtube.com/@example",
            "extra_links": [{"label": "Личный сайт", "url": "https://example.com"}],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["telegram_url"] == "https://t.me/example"
    assert body["vk_url"] == "https://vk.com/example"
    assert body["youtube_url"] == "https://youtube.com/@example"
    assert body["extra_links"] == [{"label": "Личный сайт", "url": "https://example.com"}]
    tutor_id = body["id"]

    public = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert public.status_code == 200
    public_body = public.json()
    assert public_body["telegram_url"] == "https://t.me/example"
    assert public_body["vk_url"] == "https://vk.com/example"
    assert public_body["youtube_url"] == "https://youtube.com/@example"
    assert public_body["extra_links"] == [{"label": "Личный сайт", "url": "https://example.com"}]

    # Clearing a link (explicit null) removes it.
    cleared = await client.patch("/api/v1/tutors/me", headers=tutor["headers"], json={"telegram_url": None})
    assert cleared.status_code == 200
    assert cleared.json()["telegram_url"] is None


async def test_tutor_social_link_rejects_non_url(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "bad-link-tutor@example.com")
    resp = await client.patch(
        "/api/v1/tutors/me", headers=tutor["headers"], json={"vk_url": "javascript:alert(1)"}
    )
    assert resp.status_code == 422


async def test_public_profile_booking_buttons_reflect_toggles_and_lesson_types(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "toggle-tutor@example.com")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    # No lesson types yet at all - both buttons should be hidden even though the
    # toggles themselves default to true.
    no_types = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert no_types.json()["show_individual_booking"] is False
    assert no_types.json()["show_group_booking"] is False

    await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Индивидуальное", "format": "individual", "duration_minutes": 60, "price": 1000},
    )
    group_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Групповое", "format": "group", "duration_minutes": 90, "price": 500},
    )
    group_type_id = group_type_resp.json()["id"]

    # Both toggles default to true, and lesson types now exist for both formats.
    both_resp = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert both_resp.json()["show_individual_booking"] is True
    assert both_resp.json()["show_group_booking"] is True

    # Turning the group toggle off hides only the group button.
    off_resp = await client.patch("/api/v1/tutors/me", headers=tutor["headers"], json={"allow_group_bookings": False})
    assert off_resp.status_code == 200
    after_toggle = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert after_toggle.json()["show_individual_booking"] is True
    assert after_toggle.json()["show_group_booking"] is False

    # Turning it back on but deactivating the only group lesson type still hides it -
    # the toggle alone isn't enough, there has to be something bookable.
    await client.patch("/api/v1/tutors/me", headers=tutor["headers"], json={"allow_group_bookings": True})
    await client.patch(
        f"/api/v1/tutors/me/lesson-types/{group_type_id}", headers=tutor["headers"], json={"is_active": False}
    )
    after_deactivate = await client.get(f"/api/v1/tutors/{tutor_id}")
    assert after_deactivate.json()["show_group_booking"] is False


async def test_catalog_pagination(client: AsyncClient) -> None:
    for i in range(3):
        tutor = await _register_tutor(client, f"page-tutor{i}@example.com")
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )

    page1 = await client.get("/api/v1/tutors", params={"page": 1, "page_size": 2})
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["page"] == 1
    assert body1["page_size"] == 2
    assert len(body1["items"]) == 2
    assert body1["total"] >= 3

    page2 = await client.get("/api/v1/tutors", params={"page": 2, "page_size": 2})
    body2 = page2.json()
    assert len(body2["items"]) >= 1
    # No overlap between pages.
    ids1 = {t["id"] for t in body1["items"]}
    ids2 = {t["id"] for t in body2["items"]}
    assert ids1.isdisjoint(ids2)

    bad_resp = await client.get("/api/v1/tutors", params={"page": 0})
    assert bad_resp.status_code == 422


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
    assert any(item["id"] == tutor_id for item in in_range.json()["items"])

    out_of_range = await client.get("/api/v1/tutors", params={"price_min": 5000})
    assert all(item["id"] != tutor_id for item in out_of_range.json()["items"])

    public_types = await client.get(f"/api/v1/tutors/{tutor_id}/lesson-types")
    assert public_types.status_code == 200
    assert len(public_types.json()) == 1
    assert public_types.json()[0]["price"] == 2000


async def test_catalog_item_has_about_snippet_and_booking_flag(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "catalog-about-tutor@example.com")
    long_about = "Опытный репетитор. " * 20  # comfortably over the 140-char snippet cutoff
    await client.patch(
        "/api/v1/tutors/me",
        headers=tutor["headers"],
        json={"about": f"<p>{long_about}</p><script>evil()</script>"},
    )
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    # No active individual lesson type yet: no booking button, even though "about" is set.
    no_lesson_type = await client.get("/api/v1/tutors", params={"page_size": 100})
    item = next(i for i in no_lesson_type.json()["items"] if i["id"] == tutor_id)
    assert item["show_individual_booking"] is False
    assert item["about_snippet"] is not None
    assert "evil()" not in item["about_snippet"]
    assert item["about_snippet"].endswith("…")
    assert len(item["about_snippet"]) <= 141  # 140 chars + ellipsis

    await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1500},
    )
    with_lesson_type = await client.get("/api/v1/tutors", params={"page_size": 100})
    item = next(i for i in with_lesson_type.json()["items"] if i["id"] == tutor_id)
    assert item["show_individual_booking"] is True


async def test_catalog_item_group_booking_flag(client: AsyncClient) -> None:
    """The catalog card shows "Запись на групповое занятие" under the same rule as the
    public profile: the tutor's own toggle AND an active group-format lesson type."""
    tutor = await _register_tutor(client, "catalog-group-tutor@example.com")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    async def catalog_item() -> dict:
        resp = await client.get("/api/v1/tutors", params={"page_size": 100})
        return next(i for i in resp.json()["items"] if i["id"] == tutor_id)

    # allow_group_bookings defaults to True, but without a group lesson type there is
    # nothing to sign up for.
    assert (await catalog_item())["show_group_booking"] is False

    await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
    )
    item = await catalog_item()
    assert item["show_group_booking"] is True
    # An individual-format button must not appear just because a group type exists.
    assert item["show_individual_booking"] is False

    # Turning the setting off hides the button again even though the type stays active.
    await client.patch(
        "/api/v1/tutors/me", headers=tutor["headers"], json={"allow_group_bookings": False}
    )
    assert (await catalog_item())["show_group_booking"] is False


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

    # +2 days (not +1) so the window comfortably clears the tutor's default 24h
    # min_lead_time_hours regardless of what time of day the suite happens to run at.
    date_from = dt.date.today() + dt.timedelta(days=2)
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


async def test_manual_booking_dates_and_slots_ignore_lead_time(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "manual-booking-tutor@example.com")
    # A 5h lead time would normally hide "today", but the tutor's own manual-booking
    # browser should bypass it entirely (same reasoning as admin reschedule).
    await client.patch(
        "/api/v1/tutors/me",
        headers=tutor["headers"],
        json={"min_lead_time_hours": 5},
    )
    target_date = _next_weekday(weekday=0)
    await client.put(
        "/api/v1/tutors/me/availability",
        headers=tutor["headers"],
        json={"intervals": [{"weekday": 0, "start_time": "09:00:00", "end_time": "11:00:00"}]},
    )

    date_from = dt.date.today()
    date_to = target_date
    dates_resp = await client.get(
        "/api/v1/tutors/me/manual-booking/dates",
        headers=tutor["headers"],
        params={"duration_minutes": 60, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
    )
    assert dates_resp.status_code == 200, dates_resp.text
    assert target_date.isoformat() in dates_resp.json()

    slots_resp = await client.get(
        "/api/v1/tutors/me/manual-booking/slots",
        headers=tutor["headers"],
        params={"duration_minutes": 60, "date": target_date.isoformat()},
    )
    assert slots_resp.status_code == 200, slots_resp.text
    slots = _slots_by_start(slots_resp.json())
    nine_am_utc = dt.datetime.combine(target_date, dt.time(9, 0), tzinfo=MSK).astimezone(dt.timezone.utc)
    assert slots[nine_am_utc] is True


async def test_manual_booking_availability_requires_tutor_role(client: AsyncClient) -> None:
    student_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "manual-booking-student@example.com",
            "password": "supersecret1",
            "first_name": "Уч",
            "last_name": "Еник",
            "role": "student",
            "pd_consent": True,
        },
    )
    headers = {"Authorization": f"Bearer {student_resp.json()['tokens']['access_token']}"}
    resp = await client.get(
        "/api/v1/tutors/me/manual-booking/dates",
        headers=headers,
        params={"duration_minutes": 60, "date_from": dt.date.today().isoformat(), "date_to": dt.date.today().isoformat()},
    )
    assert resp.status_code == 403


async def test_student_detail_reachable_via_booking_alone(client: AsyncClient) -> None:
    tutor = await _register_tutor(client, "student-detail-tutor@example.com")
    student_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "student-detail-student@example.com",
            "password": "supersecret1",
            "first_name": "Оля",
            "last_name": "Петрова",
            "role": "student",
            "pd_consent": True,
        },
    )
    student_body = student_resp.json()
    student_id = student_body["user"]["id"]
    student_headers = {"Authorization": f"Bearer {student_body['tokens']['access_token']}"}
    await client.patch("/api/v1/auth/me", headers=student_headers, json={"grade": 9})

    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)
    end = start + dt.timedelta(minutes=60)
    booking_resp = await client.post(
        "/api/v1/bookings/manual",
        headers=tutor["headers"],
        json={"student_id": student_id, "start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    assert booking_resp.status_code == 201, booking_resp.text

    detail_resp = await client.get(f"/api/v1/tutors/me/students/{student_id}", headers=tutor["headers"])
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["last_name"] == "Петрова"
    assert detail["grade"] == 9
    assert detail["groups"] == []


async def test_profile_video_is_validated_and_exposed_as_embed(client: AsyncClient) -> None:
    """Tutors can put a presentation video on their profile; the public profile also
    carries the ready-to-embed player URL (see app/utils/video.py)."""
    tutor = await _register_tutor(client, "video-tutor@example.com")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    saved = await client.patch(
        "/api/v1/tutors/me",
        headers=tutor["headers"],
        json={"video_url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["video_url"] == "https://youtu.be/dQw4w9WgXcQ"

    public = (await client.get(f"/api/v1/tutors/{tutor_id}")).json()
    assert public["video_url"] == "https://youtu.be/dQw4w9WgXcQ"
    assert public["video_embed_url"] == "https://www.youtube.com/embed/dQw4w9WgXcQ"

    # A link outside the supported platforms is refused rather than embedded blindly.
    rejected = await client.patch(
        "/api/v1/tutors/me", headers=tutor["headers"], json={"video_url": "https://vimeo.com/123456"}
    )
    assert rejected.status_code == 422
    assert (await client.get(f"/api/v1/tutors/{tutor_id}")).json()["video_embed_url"] is not None

    # Explicit null clears it.
    cleared = await client.patch("/api/v1/tutors/me", headers=tutor["headers"], json={"video_url": None})
    assert cleared.status_code == 200
    assert cleared.json()["video_url"] is None
    public_after = (await client.get(f"/api/v1/tutors/{tutor_id}")).json()
    assert public_after["video_url"] is None and public_after["video_embed_url"] is None
