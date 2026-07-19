import datetime as dt

from httpx import AsyncClient


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


async def _setup_tutor_with_group(
    client: AsyncClient, email: str, capacity: int = 3
) -> dict:
    tutor = await _register(client, email, "tutor")
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа подготовки", "format": "group", "duration_minutes": 90, "price": 500},
    )
    assert lesson_type_resp.status_code == 201, lesson_type_resp.text
    lesson_type_id = lesson_type_resp.json()["id"]

    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Подготовка к ЕГЭ",
            "lesson_type_id": lesson_type_id,
            "capacity": capacity,
            "meeting_link": "https://meet.example.com/group",
            "schedule_slots": [
                {"weekday": 1, "start_time": "18:00:00"},
                {"weekday": 3, "start_time": "18:00:00"},
            ],
        },
    )
    assert group_resp.status_code == 201, group_resp.text
    tutor["group"] = group_resp.json()
    tutor["lesson_type_id"] = lesson_type_id
    return tutor


async def test_group_creation_generates_occurrences(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor1@example.com")
    group_id = tutor["group"]["id"]

    occurrences_resp = await client.get(f"/api/v1/groups/{group_id}/occurrences")
    assert occurrences_resp.status_code == 200
    occurrences = occurrences_resp.json()
    assert len(occurrences) > 0
    for occ in occurrences:
        start = dt.datetime.fromisoformat(occ["start_at"].replace("Z", "+00:00"))
        weekday_msk = start.astimezone(dt.timezone(dt.timedelta(hours=3))).weekday()
        assert weekday_msk in (1, 3)
        assert occ["status"] == "scheduled"


async def test_public_group_listing(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor2@example.com")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    resp = await client.get(f"/api/v1/tutors/{tutor_id}/groups")
    assert resp.status_code == 200, resp.text
    groups = resp.json()
    assert len(groups) == 1
    assert groups[0]["price"] == 500
    assert groups[0]["duration_minutes"] == 90
    assert groups[0]["member_count"] == 0

    # Hiding the group removes it from the public listing.
    await client.patch(
        f"/api/v1/groups/{tutor['group']['id']}", headers=tutor["headers"], json={"is_active": False}
    )
    resp2 = await client.get(f"/api/v1/tutors/{tutor_id}/groups")
    assert resp2.json() == []


async def test_application_accept_reject_and_capacity(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor3@example.com", capacity=1)
    group_id = tutor["group"]["id"]
    student1 = await _register(client, "group-student3a@example.com", "student")
    student2 = await _register(client, "group-student3b@example.com", "student")

    app1 = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student1["headers"], json={})
    app2 = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student2["headers"], json={})
    assert app1.status_code == 201 and app2.status_code == 201

    applications = (await client.get(f"/api/v1/groups/{group_id}/applications", headers=tutor["headers"])).json()
    assert len(applications) == 2

    accept1 = await client.post(
        f"/api/v1/groups/{group_id}/applications/{app1.json()['id']}/accept", headers=tutor["headers"]
    )
    assert accept1.status_code == 200, accept1.text

    # Capacity is now full (1/1): accepting the second application must fail.
    accept2 = await client.post(
        f"/api/v1/groups/{group_id}/applications/{app2.json()['id']}/accept", headers=tutor["headers"]
    )
    assert accept2.status_code == 409

    reject2 = await client.post(
        f"/api/v1/groups/{group_id}/applications/{app2.json()['id']}/reject", headers=tutor["headers"]
    )
    assert reject2.status_code == 200
    assert reject2.json()["status"] == "rejected"

    my_memberships = (await client.get("/api/v1/groups/me", headers=student1["headers"])).json()
    assert len(my_memberships) == 1
    assert my_memberships[0]["group_id"] == group_id

    my_apps = (await client.get("/api/v1/groups/me/applications", headers=student2["headers"])).json()
    assert my_apps[0]["status"] == "rejected"


async def test_student_leave_and_tutor_remove(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor4@example.com", capacity=2)
    group_id = tutor["group"]["id"]
    student1 = await _register(client, "group-student4a@example.com", "student")
    student2 = await _register(client, "group-student4b@example.com", "student")

    for student in (student1, student2):
        app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
        await client.post(
            f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
        )

    members = (await client.get(f"/api/v1/groups/{group_id}/members", headers=tutor["headers"])).json()
    assert len(members) == 2

    leave_resp = await client.post(f"/api/v1/groups/{group_id}/leave", headers=student1["headers"])
    assert leave_resp.status_code == 200
    assert leave_resp.json()["status"] == "left"

    remove_resp = await client.delete(
        f"/api/v1/groups/{group_id}/members/{student2['user']['id']}", headers=tutor["headers"]
    )
    assert remove_resp.status_code == 200
    assert remove_resp.json()["status"] == "left"

    remaining = (await client.get(f"/api/v1/groups/{group_id}/members", headers=tutor["headers"])).json()
    assert remaining == []


async def test_tutor_occurrence_crud(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor5@example.com")
    group_id = tutor["group"]["id"]

    occurrences = (await client.get(f"/api/v1/groups/{group_id}/occurrences")).json()
    occurrence_id = occurrences[0]["id"]
    original_start = occurrences[0]["start_at"]

    cancel_resp = await client.patch(
        f"/api/v1/groups/{group_id}/occurrences/{occurrence_id}",
        headers=tutor["headers"],
        json={"status": "cancelled"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    second_occurrence_id = occurrences[1]["id"]
    new_start = dt.datetime.fromisoformat(occurrences[1]["start_at"].replace("Z", "+00:00")) + dt.timedelta(hours=2)
    new_end = dt.datetime.fromisoformat(occurrences[1]["end_at"].replace("Z", "+00:00")) + dt.timedelta(hours=2)
    reschedule_resp = await client.patch(
        f"/api/v1/groups/{group_id}/occurrences/{second_occurrence_id}",
        headers=tutor["headers"],
        json={"start_at": new_start.isoformat(), "end_at": new_end.isoformat()},
    )
    assert reschedule_resp.status_code == 200, reschedule_resp.text
    assert reschedule_resp.json()["status"] == "rescheduled"
    assert reschedule_resp.json()["original_start_at"] is not None

    delete_resp = await client.delete(
        f"/api/v1/groups/{group_id}/occurrences/{occurrences[2]['id']}", headers=tutor["headers"]
    )
    assert delete_resp.status_code == 204

    remaining = (await client.get(f"/api/v1/groups/{group_id}/occurrences")).json()
    assert occurrences[2]["id"] not in [o["id"] for o in remaining]
    assert original_start == occurrences[0]["start_at"]  # sanity: unchanged before our patch above
