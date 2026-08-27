from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
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


async def test_non_admin_gets_403(client: AsyncClient) -> None:
    tutor = await _register(client, "adm-tutor0@example.com", "tutor")
    resp = await client.get("/api/v1/admin/tutors", headers=tutor["headers"])
    assert resp.status_code == 403


async def test_admin_tutor_crud(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session)
    tutor = await _register(client, "adm-tutor1@example.com", "tutor")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    list_resp = await client.get("/api/v1/admin/tutors", headers=admin_headers)
    assert list_resp.status_code == 200
    assert any(t["id"] == tutor_id for t in list_resp.json())

    patch_resp = await client.patch(
        f"/api/v1/admin/tutors/{tutor_id}",
        headers=admin_headers,
        json={"first_name": "Renamed", "last_name": "Tutor", "is_active": False, "about": "Опытный репетитор"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["display_name"] == "Tutor Renamed"
    assert patch_resp.json()["about"] == "Опытный репетитор"

    # Deactivated tutor can no longer log in.
    login_resp = await client.post(
        "/api/v1/auth/login", headers={}, json={"email": "adm-tutor1@example.com", "password": "supersecret1"}
    )
    assert login_resp.status_code == 403

    delete_resp = await client.delete(f"/api/v1/admin/tutors/{tutor_id}", headers=admin_headers)
    assert delete_resp.status_code == 204
    assert (await client.get(f"/api/v1/admin/tutors/{tutor_id}", headers=admin_headers)).status_code == 404


async def test_admin_student_crud(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session)
    student = await _register(client, "adm-student1@example.com", "student")
    student_id = student["user"]["id"]

    list_resp = await client.get("/api/v1/admin/students", headers=admin_headers)
    assert any(s["id"] == student_id for s in list_resp.json())

    patch_resp = await client.patch(
        f"/api/v1/admin/students/{student_id}",
        headers=admin_headers,
        json={"first_name": "Renamed", "last_name": "Student"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["display_name"] == "Student Renamed"

    delete_resp = await client.delete(f"/api/v1/admin/students/{student_id}", headers=admin_headers)
    assert delete_resp.status_code == 204
    assert (await client.get(f"/api/v1/admin/students/{student_id}", headers=admin_headers)).status_code == 404


async def test_admin_tutor_edit_full_profile_and_email_change(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-tutoredit@example.com")
    tutor = await _register(client, "adm-tutor4@example.com", "tutor")
    await _register(client, "adm-tutor4b@example.com", "tutor")  # reserves the email used in the duplicate check below
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    # Prefilling an edit form needs first_name/last_name/patronymic/email split out,
    # not just the denormalized display_name.
    get_resp = await client.get(f"/api/v1/admin/tutors/{tutor_id}", headers=admin_headers)
    assert get_resp.json()["first_name"] == "Test"
    assert get_resp.json()["email"] == "adm-tutor4@example.com"

    patch_resp = await client.patch(
        f"/api/v1/admin/tutors/{tutor_id}",
        headers=admin_headers,
        json={
            "about": "<b>Про меня</b>",
            "is_hidden": True,
            "cancel_min_hours_before": 12,
            "cancel_max_per_month": 2,
            "reschedule_min_hours_before": 6,
            "reschedule_max_per_month": 3,
            "email": "adm-tutor4-new@example.com",
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["about"] == "<b>Про меня</b>"
    assert body["is_hidden"] is True
    assert body["cancel_min_hours_before"] == 12
    assert body["email"] == "adm-tutor4-new@example.com"

    # Email change resets verification, same as self-service.
    me_resp = await client.get("/api/v1/auth/me", headers=tutor["headers"])
    assert me_resp.json()["email"] == "adm-tutor4-new@example.com"
    assert me_resp.json()["email_verified"] is False

    # Can't set a duplicate email.
    dup_resp = await client.patch(
        f"/api/v1/admin/tutors/{tutor_id}", headers=admin_headers, json={"email": "adm-tutor4b@example.com"}
    )
    assert dup_resp.status_code == 409


async def test_admin_student_edit_full_profile(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-studentedit@example.com")
    student = await _register(client, "adm-student4@example.com", "student")
    student_id = student["user"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/admin/students/{student_id}",
        headers=admin_headers,
        json={"grade": 9, "timezone": "Asia/Yekaterinburg", "email": "adm-student4-new@example.com"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["grade"] == 9
    assert body["timezone"] == "Asia/Yekaterinburg"
    assert body["email"] == "adm-student4-new@example.com"
    assert body["email_verified"] is False


async def test_admin_reschedule_booking(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-reschedule@example.com")
    tutor = await _register(client, "adm-tutor5@example.com", "tutor")
    student = await _register(client, "adm-student5@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    start_at = datetime.now(timezone.utc) + timedelta(days=3)
    end_at = start_at + timedelta(hours=1)
    create_resp = await client.post(
        "/api/v1/admin/bookings",
        headers=admin_headers,
        json={
            "tutor_id": tutor_id,
            "student_id": student["user"]["id"],
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        },
    )
    booking_id = create_resp.json()["id"]

    new_start = start_at + timedelta(hours=5)
    reschedule_resp = await client.post(
        f"/api/v1/admin/bookings/{booking_id}/reschedule",
        headers=admin_headers,
        json={"new_start_at": new_start.isoformat()},
    )
    assert reschedule_resp.status_code == 200, reschedule_resp.text
    new_booking = reschedule_resp.json()
    assert new_booking["status"] == "scheduled"
    assert new_booking["rescheduled_from_id"] == booking_id
    # Duration (1h) preserved from the original booking.
    new_start_dt = datetime.fromisoformat(new_booking["start_at"].replace("Z", "+00:00"))
    new_end_dt = datetime.fromisoformat(new_booking["end_at"].replace("Z", "+00:00"))
    assert new_end_dt - new_start_dt == timedelta(hours=1)

    old_resp = await client.get("/api/v1/admin/bookings", headers=admin_headers, params={"tutor_id": tutor_id})
    old_booking = next(b for b in old_resp.json()["items"] if b["id"] == booking_id)
    assert old_booking["status"] == "rescheduled"
    assert old_booking["cancelled_by"] == "admin"

    # Rescheduling an already-rescheduled (no longer scheduled) booking fails.
    again_resp = await client.post(
        f"/api/v1/admin/bookings/{booking_id}/reschedule",
        headers=admin_headers,
        json={"new_start_at": (new_start + timedelta(hours=1)).isoformat()},
    )
    assert again_resp.status_code == 409


async def test_admin_reschedule_rejects_conflicting_slot(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-reschedule2@example.com")
    tutor = await _register(client, "adm-tutor6@example.com", "tutor")
    student = await _register(client, "adm-student6@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    base_start = datetime.now(timezone.utc) + timedelta(days=3)
    other_start = base_start + timedelta(hours=3)

    booking_a = (
        await client.post(
            "/api/v1/admin/bookings",
            headers=admin_headers,
            json={
                "tutor_id": tutor_id,
                "student_id": student["user"]["id"],
                "start_at": base_start.isoformat(),
                "end_at": (base_start + timedelta(hours=1)).isoformat(),
            },
        )
    ).json()
    await client.post(
        "/api/v1/admin/bookings",
        headers=admin_headers,
        json={
            "tutor_id": tutor_id,
            "student_id": student["user"]["id"],
            "start_at": other_start.isoformat(),
            "end_at": (other_start + timedelta(hours=1)).isoformat(),
        },
    )

    conflict_resp = await client.post(
        f"/api/v1/admin/bookings/{booking_a['id']}/reschedule",
        headers=admin_headers,
        json={"new_start_at": other_start.isoformat()},
    )
    assert conflict_resp.status_code == 409


async def test_admin_add_and_remove_group_member_directly(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-groupadd@example.com")
    tutor = await _register(client, "adm-tutor7@example.com", "tutor")
    student1 = await _register(client, "adm-student7a@example.com", "student")
    student2 = await _register(client, "adm-student7b@example.com", "student")

    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
    )
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Direct-add group",
            "lesson_type_id": lesson_type_resp.json()["id"],
            "capacity": 1,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]

    add_resp = await client.post(
        f"/api/v1/admin/groups/{group_id}/members",
        headers=admin_headers,
        json={"student_id": student1["user"]["id"]},
    )
    assert add_resp.status_code == 201, add_resp.text
    assert add_resp.json()["status"] == "active"

    # Already a member.
    dup_resp = await client.post(
        f"/api/v1/admin/groups/{group_id}/members",
        headers=admin_headers,
        json={"student_id": student1["user"]["id"]},
    )
    assert dup_resp.status_code == 409

    # Capacity (1) already full.
    full_resp = await client.post(
        f"/api/v1/admin/groups/{group_id}/members",
        headers=admin_headers,
        json={"student_id": student2["user"]["id"]},
    )
    assert full_resp.status_code == 409

    members_resp = await client.get(f"/api/v1/admin/groups/{group_id}/members", headers=admin_headers)
    assert len(members_resp.json()) == 1

    # Free up the seat, then re-add the same (now former) member.
    await client.delete(f"/api/v1/admin/groups/{group_id}/members/{student1['user']['id']}", headers=admin_headers)
    readd_resp = await client.post(
        f"/api/v1/admin/groups/{group_id}/members",
        headers=admin_headers,
        json={"student_id": student1["user"]["id"]},
    )
    assert readd_resp.status_code == 201, readd_resp.text
    assert readd_resp.json()["status"] == "active"


async def test_admin_booking_crud_across_any_tutor(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session)
    tutor = await _register(client, "adm-tutor2@example.com", "tutor")
    student = await _register(client, "adm-student2@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    start_at = datetime.now(timezone.utc) + timedelta(days=3)
    end_at = start_at + timedelta(hours=1)
    create_resp = await client.post(
        "/api/v1/admin/bookings",
        headers=admin_headers,
        json={
            "tutor_id": tutor_id,
            "student_id": student["user"]["id"],
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "notes": "created by admin",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    booking_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/admin/bookings", headers=admin_headers, params={"tutor_id": tutor_id})
    assert any(b["id"] == booking_id for b in list_resp.json()["items"])

    patch_resp = await client.patch(
        f"/api/v1/admin/bookings/{booking_id}", headers=admin_headers, json={"notes": "updated by admin"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["notes"] == "updated by admin"

    delete_resp = await client.delete(f"/api/v1/admin/bookings/{booking_id}", headers=admin_headers)
    assert delete_resp.status_code == 204


async def test_admin_group_and_membership_management(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session)
    tutor = await _register(client, "adm-tutor3@example.com", "tutor")
    student = await _register(client, "adm-student3@example.com", "student")

    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
    )
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Admin-managed group",
            "lesson_type_id": lesson_type_resp.json()["id"],
            "capacity": 2,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]

    list_resp = await client.get("/api/v1/admin/groups", headers=admin_headers)
    assert any(g["id"] == group_id for g in list_resp.json())

    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    application_id = app_resp.json()["id"]

    apps_resp = await client.get(f"/api/v1/admin/groups/{group_id}/applications", headers=admin_headers)
    assert len(apps_resp.json()) == 1

    accept_resp = await client.post(
        f"/api/v1/admin/groups/{group_id}/applications/{application_id}/accept", headers=admin_headers
    )
    assert accept_resp.status_code == 200, accept_resp.text

    members_resp = await client.get(f"/api/v1/admin/groups/{group_id}/members", headers=admin_headers)
    assert len(members_resp.json()) == 1

    remove_resp = await client.delete(
        f"/api/v1/admin/groups/{group_id}/members/{student['user']['id']}", headers=admin_headers
    )
    assert remove_resp.status_code == 200
    assert remove_resp.json()["status"] == "left"
    assert remove_resp.json()["left_by"] == "admin"

    update_resp = await client.patch(
        f"/api/v1/admin/groups/{group_id}", headers=admin_headers, json={"name": "Renamed group", "is_active": False}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False
    assert update_resp.json()["name"] == "Renamed group"

    delete_resp = await client.delete(f"/api/v1/admin/groups/{group_id}", headers=admin_headers)
    assert delete_resp.status_code == 204


async def test_admin_reassign_group_tutor(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-reassign@example.com")
    tutor_a = await _register(client, "adm-tutor8a@example.com", "tutor")
    tutor_b = await _register(client, "adm-tutor8b@example.com", "tutor")

    lesson_type_a = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor_a["headers"],
            json={"name": "Группа A", "format": "group", "duration_minutes": 90, "price": 500},
        )
    ).json()
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor_a["headers"],
        json={
            "name": "Reassignable group",
            "lesson_type_id": lesson_type_a["id"],
            "capacity": 2,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]
    tutor_a_id = (await client.get("/api/v1/tutors/me", headers=tutor_a["headers"])).json()["id"]
    tutor_b_id = (await client.get("/api/v1/tutors/me", headers=tutor_b["headers"])).json()["id"]

    # Tutor B has no group-format lesson type yet - reassigning to a lesson type that
    # doesn't belong to them (or doesn't exist) must fail.
    bad_resp = await client.post(
        f"/api/v1/admin/groups/{group_id}/reassign-tutor",
        headers=admin_headers,
        json={"tutor_id": tutor_b_id, "lesson_type_id": lesson_type_a["id"]},
    )
    assert bad_resp.status_code == 404

    lesson_type_b = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor_b["headers"],
            json={"name": "Группа B", "format": "group", "duration_minutes": 60, "price": 400},
        )
    ).json()
    good_resp = await client.post(
        f"/api/v1/admin/groups/{group_id}/reassign-tutor",
        headers=admin_headers,
        json={"tutor_id": tutor_b_id, "lesson_type_id": lesson_type_b["id"]},
    )
    assert good_resp.status_code == 200, good_resp.text
    assert good_resp.json()["tutor_id"] == tutor_b_id
    assert good_resp.json()["lesson_type_id"] == lesson_type_b["id"]
    assert good_resp.json()["tutor_id"] != tutor_a_id


async def test_admin_reschedule_dates_and_slots_with_duration_override(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-reschedule-browse@example.com")
    tutor = await _register(client, "adm-tutor9@example.com", "tutor")
    student = await _register(client, "adm-student9@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    await client.put(
        "/api/v1/tutors/me/availability",
        headers=tutor["headers"],
        json={"intervals": [{"weekday": w, "start_time": "09:00:00", "end_time": "18:00:00"} for w in range(7)]},
    )

    start_at = datetime.now(timezone.utc) + timedelta(days=3)
    start_at = start_at.replace(hour=10, minute=0, second=0, microsecond=0)
    end_at = start_at + timedelta(hours=1)
    booking_id = (
        await client.post(
            "/api/v1/admin/bookings",
            headers=admin_headers,
            json={
                "tutor_id": tutor_id,
                "student_id": student["user"]["id"],
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
            },
        )
    ).json()["id"]

    date_from = start_at.date().isoformat()
    date_to = (start_at + timedelta(days=10)).date().isoformat()
    dates_resp = await client.get(
        f"/api/v1/admin/bookings/{booking_id}/reschedule/dates",
        headers=admin_headers,
        params={"date_from": date_from, "date_to": date_to},
    )
    assert dates_resp.status_code == 200, dates_resp.text
    assert len(dates_resp.json()) > 0

    slots_resp = await client.get(
        f"/api/v1/admin/bookings/{booking_id}/reschedule/slots",
        headers=admin_headers,
        params={"date": date_from},
    )
    assert slots_resp.status_code == 200
    assert any(s["available"] for s in slots_resp.json())

    # A longer duration should yield fewer (or equal) available slots that day.
    long_slots_resp = await client.get(
        f"/api/v1/admin/bookings/{booking_id}/reschedule/slots",
        headers=admin_headers,
        params={"date": date_from, "duration_minutes": 480},
    )
    assert long_slots_resp.status_code == 200
    long_available = sum(1 for s in long_slots_resp.json() if s["available"])
    short_available = sum(1 for s in slots_resp.json() if s["available"])
    assert long_available <= short_available

    new_date_slots = slots_resp.json()
    target_slot = next(s for s in new_date_slots if s["available"])
    reschedule_resp = await client.post(
        f"/api/v1/admin/bookings/{booking_id}/reschedule",
        headers=admin_headers,
        json={"new_start_at": target_slot["start_at"], "duration_minutes": 120},
    )
    assert reschedule_resp.status_code == 200, reschedule_resp.text
    new_booking = reschedule_resp.json()
    new_start_dt = datetime.fromisoformat(new_booking["start_at"].replace("Z", "+00:00"))
    new_end_dt = datetime.fromisoformat(new_booking["end_at"].replace("Z", "+00:00"))
    assert new_end_dt - new_start_dt == timedelta(minutes=120)


async def test_admin_bookings_date_range_filter(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-date-filter@example.com")
    tutor = await _register(client, "adm-tutor10@example.com", "tutor")
    student = await _register(client, "adm-student10@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    near_start = datetime.now(timezone.utc) + timedelta(days=1)
    far_start = datetime.now(timezone.utc) + timedelta(days=20)
    near_id = (
        await client.post(
            "/api/v1/admin/bookings",
            headers=admin_headers,
            json={
                "tutor_id": tutor_id,
                "student_id": student["user"]["id"],
                "start_at": near_start.isoformat(),
                "end_at": (near_start + timedelta(hours=1)).isoformat(),
            },
        )
    ).json()["id"]
    far_id = (
        await client.post(
            "/api/v1/admin/bookings",
            headers=admin_headers,
            json={
                "tutor_id": tutor_id,
                "student_id": student["user"]["id"],
                "start_at": far_start.isoformat(),
                "end_at": (far_start + timedelta(hours=1)).isoformat(),
            },
        )
    ).json()["id"]

    filtered_resp = await client.get(
        "/api/v1/admin/bookings",
        headers=admin_headers,
        params={
            "tutor_id": tutor_id,
            "date_from": datetime.now(timezone.utc).isoformat(),
            "date_to": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        },
    )
    assert filtered_resp.status_code == 200
    filtered_ids = {b["id"] for b in filtered_resp.json()["items"]}
    assert near_id in filtered_ids
    assert far_id not in filtered_ids


async def test_admin_bookings_subject_direction_grade_filters_and_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_headers = await _admin_headers(client, db_session, email="admin-booking-filters@example.com")
    math_tutor = await _register(client, "adm-tutor11a@example.com", "tutor")
    music_tutor = await _register(client, "adm-tutor11b@example.com", "tutor")
    student10 = await _register(client, "adm-student11a@example.com", "student")
    student11 = await _register(client, "adm-student11b@example.com", "student")
    await client.patch("/api/v1/admin/students/" + student10["user"]["id"], headers=admin_headers, json={"grade": 10})
    await client.patch("/api/v1/admin/students/" + student11["user"]["id"], headers=admin_headers, json={"grade": 11})

    subject_resp = await client.post("/api/v1/admin/subjects", headers=admin_headers, json={"name": "Математика 11"})
    subject_id = subject_resp.json()["id"]
    direction_resp = await client.post(
        f"/api/v1/admin/subjects/{subject_id}/directions", headers=admin_headers, json={"name": "ЕГЭ 11"}
    )
    direction_id = direction_resp.json()["id"]

    math_tutor_id = (await client.get("/api/v1/tutors/me", headers=math_tutor["headers"])).json()["id"]
    music_tutor_id = (await client.get("/api/v1/tutors/me", headers=music_tutor["headers"])).json()["id"]
    await client.put(
        "/api/v1/tutors/me/subjects",
        headers=math_tutor["headers"],
        json={"selections": [{"subject_id": subject_id, "direction_ids": [direction_id]}]},
    )

    start_at = datetime.now(timezone.utc) + timedelta(days=3)
    math_booking_id = (
        await client.post(
            "/api/v1/admin/bookings",
            headers=admin_headers,
            json={
                "tutor_id": math_tutor_id,
                "student_id": student10["user"]["id"],
                "start_at": start_at.isoformat(),
                "end_at": (start_at + timedelta(hours=1)).isoformat(),
            },
        )
    ).json()["id"]
    music_booking_id = (
        await client.post(
            "/api/v1/admin/bookings",
            headers=admin_headers,
            json={
                "tutor_id": music_tutor_id,
                "student_id": student11["user"]["id"],
                "start_at": (start_at + timedelta(hours=2)).isoformat(),
                "end_at": (start_at + timedelta(hours=3)).isoformat(),
            },
        )
    ).json()["id"]

    by_subject = await client.get("/api/v1/admin/bookings", headers=admin_headers, params={"subject_id": subject_id})
    by_subject_ids = {b["id"] for b in by_subject.json()["items"]}
    assert math_booking_id in by_subject_ids
    assert music_booking_id not in by_subject_ids

    by_direction = await client.get(
        "/api/v1/admin/bookings", headers=admin_headers, params={"direction_id": direction_id}
    )
    assert math_booking_id in {b["id"] for b in by_direction.json()["items"]}

    by_grade = await client.get("/api/v1/admin/bookings", headers=admin_headers, params={"grade": 10})
    by_grade_ids = {b["id"] for b in by_grade.json()["items"]}
    assert math_booking_id in by_grade_ids
    assert music_booking_id not in by_grade_ids

    # tutor_display_name is populated with the full name (unlike the "Имя Отчество"
    # format used on student-facing responses).
    math_item = next(b for b in by_subject.json()["items"] if b["id"] == math_booking_id)
    assert math_item["tutor_display_name"] == math_tutor["user"]["display_name"]

    page1 = await client.get("/api/v1/admin/bookings", headers=admin_headers, params={"page": 1, "page_size": 1})
    body1 = page1.json()
    assert body1["page"] == 1
    assert body1["page_size"] == 1
    assert len(body1["items"]) == 1
    assert body1["total"] >= 2


async def test_admin_resets_password_and_kills_existing_sessions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Последняя линия поддержки, когда письмо со ссылкой сброса до человека не
    доходит. Одна ручка на любую роль: у TutorProfileOut есть user_id, поэтому обе
    вкладки админки ходят сюда же."""
    headers = await _admin_headers(client, db_session, "admin-password@example.com")
    student = await _register(client, "reset-me@example.com", "student")
    old_refresh = (
        await client.post(
            "/api/v1/auth/login", json={"email": "reset-me@example.com", "password": "supersecret1"}
        )
    ).json()["refresh_token"]

    resp = await client.post(
        f"/api/v1/admin/users/{student['user']['id']}/password",
        headers=headers,
        json={"new_password": "brandnewpass9"},
    )
    assert resp.status_code == 204, resp.text

    # Старый пароль больше не работает, новый - работает.
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": "reset-me@example.com", "password": "supersecret1"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": "reset-me@example.com", "password": "brandnewpass9"}
        )
    ).status_code == 200

    # Выданные ранее refresh-токены отозваны: смена пароля обрывает чужие сессии.
    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 401

    # Владелец аккаунта узнаёт о смене пароля из системных уведомлений.
    login = await client.post(
        "/api/v1/auth/login", json={"email": "reset-me@example.com", "password": "brandnewpass9"}
    )
    student_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    notifications = await client.get("/api/v1/notifications/system", headers=student_headers)
    assert notifications.status_code == 200, notifications.text
    assert any(n["event_type"] == "password_changed_by_admin" for n in notifications.json())


async def test_admin_password_reset_enforces_the_same_rules_as_registration(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _admin_headers(client, db_session, "admin-password-rules@example.com")
    student = await _register(client, "weak-password@example.com", "student")

    short = await client.post(
        f"/api/v1/admin/users/{student['user']['id']}/password",
        headers=headers,
        json={"new_password": "korotk"},
    )
    assert short.status_code == 422

    # Старый пароль остался рабочим - неудачная попытка ничего не сломала.
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": "weak-password@example.com", "password": "supersecret1"}
        )
    ).status_code == 200


async def test_admin_password_reset_unlocks_a_locked_out_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Иначе сброс был бы бесполезен ровно в том случае, ради которого его и зовут:
    человек перебирал пароли, упёрся в блокировку на 15 минут и просит помощи."""
    headers = await _admin_headers(client, db_session, "admin-unlock@example.com")
    student = await _register(client, "locked-out@example.com", "student")
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login", json={"email": "locked-out@example.com", "password": "wrongpass1"}
        )
    locked = await client.post(
        "/api/v1/auth/login", json={"email": "locked-out@example.com", "password": "supersecret1"}
    )
    assert locked.status_code == 429

    await client.post(
        f"/api/v1/admin/users/{student['user']['id']}/password",
        headers=headers,
        json={"new_password": "brandnewpass9"},
    )
    unlocked = await client.post(
        "/api/v1/auth/login", json={"email": "locked-out@example.com", "password": "brandnewpass9"}
    )
    assert unlocked.status_code == 200, unlocked.text


async def test_admin_password_reset_is_admin_only(client: AsyncClient) -> None:
    student = await _register(client, "not-an-admin@example.com", "student")
    resp = await client.post(
        f"/api/v1/admin/users/{student['user']['id']}/password",
        headers=student["headers"],
        json={"new_password": "brandnewpass9"},
    )
    assert resp.status_code == 403
