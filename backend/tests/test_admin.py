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
    assert any(b["id"] == booking_id for b in list_resp.json())

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

    update_resp = await client.patch(
        f"/api/v1/admin/groups/{group_id}", headers=admin_headers, json={"is_active": False}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    delete_resp = await client.delete(f"/api/v1/admin/groups/{group_id}", headers=admin_headers)
    assert delete_resp.status_code == 204
