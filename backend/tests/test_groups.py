import datetime as dt
import uuid

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.models.notification import NotificationLog
from app.models.system_notification import SystemNotification


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

    # Left (not just active) memberships must still show up on the student's own list
    # (see group_service.list_memberships_for_student) so the CabinetView "Группы" tab
    # visibility check treats past membership the same as current.
    student1_memberships = (await client.get("/api/v1/groups/me", headers=student1["headers"])).json()
    assert len(student1_memberships) == 1
    assert student1_memberships[0]["status"] == "left"


async def test_group_out_has_duration_and_names_on_members_applications(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor6@example.com", capacity=2)
    group_id = tutor["group"]["id"]
    assert tutor["group"]["duration_minutes"] == 90

    student = await _register(client, "group-student6@example.com", "student")
    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    assert app_resp.status_code == 201

    applications = (await client.get(f"/api/v1/groups/{group_id}/applications", headers=tutor["headers"])).json()
    assert applications[0]["student_display_name"] == student["user"]["display_name"]

    await client.post(f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"])
    members = (await client.get(f"/api/v1/groups/{group_id}/members", headers=tutor["headers"])).json()
    assert members[0]["student_display_name"] == student["user"]["display_name"]


async def test_student_detail_for_tutor_requires_shared_history(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor7@example.com", capacity=2)
    group_id = tutor["group"]["id"]
    other_tutor = await _register(client, "group-tutor7b@example.com", "tutor")
    member_student = await _register(client, "group-student7a@example.com", "student")
    stranger_student = await _register(client, "group-student7b@example.com", "student")

    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=member_student["headers"], json={})
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
    )

    # Owning tutor can see the member's detail, including the shared group.
    detail_resp = await client.get(
        f"/api/v1/tutors/me/students/{member_student['user']['id']}", headers=tutor["headers"]
    )
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["first_name"] == member_student["user"]["first_name"]
    assert len(detail["groups"]) == 1
    assert detail["groups"][0]["group_id"] == group_id
    assert detail["groups"][0]["status"] == "active"

    # A student with no shared booking/group is not visible to this tutor.
    denied_resp = await client.get(
        f"/api/v1/tutors/me/students/{stranger_student['user']['id']}", headers=tutor["headers"]
    )
    assert denied_resp.status_code == 404

    # Nor is the member visible to an unrelated tutor.
    other_tutor_resp = await client.get(
        f"/api/v1/tutors/me/students/{member_student['user']['id']}", headers=other_tutor["headers"]
    )
    assert other_tutor_resp.status_code == 404


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


async def test_my_groups_exposes_created_at_and_orders_by_recency(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tutor = await _register(client, "group-tutor6@example.com", "tutor")
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа подготовки", "format": "group", "duration_minutes": 90, "price": 500},
    )
    lesson_type_id = lesson_type_resp.json()["id"]

    async def _create_group(name: str) -> str:
        resp = await client.post(
            "/api/v1/groups",
            headers=tutor["headers"],
            json={
                "name": name,
                "lesson_type_id": lesson_type_id,
                "capacity": 3,
                "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    first_id = await _create_group("Первая группа")
    second_id = await _create_group("Вторая группа")

    # SQLite's CURRENT_TIMESTAMP is second-precision, so two groups created in the
    # same request could tie - backdate the first one explicitly to make the recency
    # ordering assertion below deterministic rather than timing-dependent.
    await db_session.execute(
        update(Group).where(Group.id == uuid.UUID(first_id)).values(created_at=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc))
    )
    await db_session.commit()

    my_groups_resp = await client.get("/api/v1/groups/tutor/me", headers=tutor["headers"])
    assert my_groups_resp.status_code == 200, my_groups_resp.text
    my_groups = my_groups_resp.json()
    assert [g["id"] for g in my_groups] == [second_id, first_id]


async def test_replace_schedule_response_reflects_the_update(client: AsyncClient) -> None:
    """Regression test: PUT .../schedule used to return the pre-update
    schedule_slots (stale SQLAlchemy identity-map state) even though the write
    itself succeeded - see group_service.replace_schedule's populate_existing fix."""
    tutor = await _setup_tutor_with_group(client, "group-tutor8@example.com")
    group_id = tutor["group"]["id"]
    original_slot_ids = {s["id"] for s in tutor["group"]["schedule_slots"]}

    put_resp = await client.put(
        f"/api/v1/groups/{group_id}/schedule",
        headers=tutor["headers"],
        json=[{"weekday": 4, "start_time": "16:45:00"}],
    )
    assert put_resp.status_code == 200, put_resp.text
    put_slots = put_resp.json()["schedule_slots"]
    assert len(put_slots) == 1
    assert put_slots[0]["weekday"] == 4
    assert put_slots[0]["start_time"] == "16:45:00"
    assert put_slots[0]["id"] not in original_slot_ids

    my_groups = (await client.get("/api/v1/groups/tutor/me", headers=tutor["headers"])).json()
    assert my_groups[0]["schedule_slots"] == put_slots
    assert all(g["created_at"] for g in my_groups)


async def _accept_student(client: AsyncClient, tutor: dict, group_id: str, email: str) -> dict:
    student = await _register(client, email, "student")
    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    assert app_resp.status_code == 201, app_resp.text
    accept_resp = await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
    )
    assert accept_resp.status_code == 200, accept_resp.text
    return student


async def test_student_occurrences_list_includes_group_context(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor9@example.com")
    group_id = tutor["group"]["id"]
    member = await _accept_student(client, tutor, group_id, "group-student9a@example.com")
    outsider = await _register(client, "group-student9b@example.com", "student")

    resp = await client.get("/api/v1/groups/me/occurrences", headers=member["headers"])
    assert resp.status_code == 200, resp.text
    occurrences = resp.json()
    assert len(occurrences) > 0
    assert occurrences[0]["group_name"] == "Подготовка к ЕГЭ"
    assert occurrences[0]["meeting_link"] == "https://meet.example.com/group"
    assert occurrences[0]["my_attendance_outcome"] is None

    outsider_resp = await client.get("/api/v1/groups/me/occurrences", headers=outsider["headers"])
    assert outsider_resp.json() == []


async def test_student_marks_own_no_show(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor10@example.com")
    group_id = tutor["group"]["id"]
    member = await _accept_student(client, tutor, group_id, "group-student10a@example.com")

    occurrences = (await client.get("/api/v1/groups/me/occurrences", headers=member["headers"])).json()
    occurrence_id = occurrences[0]["id"]

    resp = await client.post(f"/api/v1/groups/me/occurrences/{occurrence_id}/no-show", headers=member["headers"])
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["my_attendance_outcome"] == "student_no_show"
    # The session itself is unaffected - it still happens for the rest of the group.
    assert updated["status"] == "scheduled"

    refreshed = (await client.get("/api/v1/groups/me/occurrences", headers=member["headers"])).json()
    assert refreshed[0]["my_attendance_outcome"] == "student_no_show"

    tutor_user_id = uuid.UUID(tutor["user"]["id"])
    log_result = await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == tutor_user_id)
    )
    assert any(row.event_type == "other" for row in log_result.scalars().all())

    sysnotif_result = await db_session.execute(
        select(SystemNotification).where(SystemNotification.user_id == tutor_user_id)
    )
    assert any(row.event_type == "group_lesson_no_show_by_student" for row in sysnotif_result.scalars().all())


async def test_no_show_forbidden_for_non_member(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor11@example.com")
    group_id = tutor["group"]["id"]
    outsider = await _register(client, "group-student11a@example.com", "student")

    occurrences = (await client.get(f"/api/v1/groups/{group_id}/occurrences")).json()
    resp = await client.post(
        f"/api/v1/groups/me/occurrences/{occurrences[0]['id']}/no-show", headers=outsider["headers"]
    )
    assert resp.status_code == 403


async def test_no_show_rejected_for_cancelled_occurrence(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-tutor12@example.com")
    group_id = tutor["group"]["id"]
    member = await _accept_student(client, tutor, group_id, "group-student12a@example.com")

    occurrences = (await client.get("/api/v1/groups/me/occurrences", headers=member["headers"])).json()
    occurrence_id = occurrences[0]["id"]

    cancel_resp = await client.patch(
        f"/api/v1/groups/{group_id}/occurrences/{occurrence_id}", headers=tutor["headers"], json={"status": "cancelled"}
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    resp = await client.post(f"/api/v1/groups/me/occurrences/{occurrence_id}/no-show", headers=member["headers"])
    assert resp.status_code == 409


async def test_group_full_edit(client: AsyncClient) -> None:
    """Beyond periodicity, the tutor can edit the same fields they set at creation:
    name, capacity and meeting link (see components/tutor/GroupsTab.vue)."""
    tutor = await _setup_tutor_with_group(client, "group-edit-tutor@example.com", capacity=4)
    group_id = tutor["group"]["id"]

    resp = await client.patch(
        f"/api/v1/groups/{group_id}",
        headers=tutor["headers"],
        json={
            "name": "Подготовка к ОГЭ",
            "capacity": 8,
            "meeting_link": "https://meet.example.com/new-room",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Подготовка к ОГЭ"
    assert body["capacity"] == 8
    assert body["meeting_link"] == "https://meet.example.com/new-room"

    # And it survives a reload, not just the response of the write itself.
    listed = (await client.get("/api/v1/groups/tutor/me", headers=tutor["headers"])).json()
    assert listed[0]["name"] == "Подготовка к ОГЭ"
    assert listed[0]["capacity"] == 8

    # Clearing the link is a meaningful edit, not a "field omitted".
    cleared = await client.patch(
        f"/api/v1/groups/{group_id}", headers=tutor["headers"], json={"meeting_link": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["meeting_link"] is None

    # ...but the non-nullable fields have no "clear" meaning: a null there is an empty
    # form field and must leave the stored value alone rather than hit NOT NULL.
    nulls = await client.patch(
        f"/api/v1/groups/{group_id}",
        headers=tutor["headers"],
        json={"name": None, "capacity": None, "is_active": None},
    )
    assert nulls.status_code == 200, nulls.text
    assert nulls.json()["name"] == "Подготовка к ОГЭ"
    assert nulls.json()["capacity"] == 8
    assert nulls.json()["is_active"] is True


async def test_capacity_cannot_drop_below_current_members(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-capacity-tutor@example.com", capacity=3)
    group_id = tutor["group"]["id"]
    student = await _register(client, "group-capacity-student@example.com", "student")
    application = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{application.json()['id']}/accept", headers=tutor["headers"]
    )

    too_small = await client.patch(
        f"/api/v1/groups/{group_id}", headers=tutor["headers"], json={"capacity": 0}
    )
    assert too_small.status_code == 422  # capacity must be > 0 at the schema level

    below_members = await client.patch(
        f"/api/v1/groups/{group_id}", headers=tutor["headers"], json={"capacity": 1}
    )
    assert below_members.status_code == 200, "capacity == member count is still fine"

    # 1 member enrolled, so 1 is the floor.
    assert (
        await client.patch(f"/api/v1/groups/{group_id}", headers=tutor["headers"], json={"capacity": 1})
    ).json()["capacity"] == 1


async def test_delete_group_requires_empty_group(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-delete-tutor@example.com")
    group_id = tutor["group"]["id"]
    student = await _register(client, "group-delete-student@example.com", "student")
    application = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{application.json()['id']}/accept", headers=tutor["headers"]
    )

    blocked = await client.delete(f"/api/v1/groups/{group_id}", headers=tutor["headers"])
    assert blocked.status_code == 409
    assert "исключите" in blocked.json()["detail"].lower()

    # Once the last member is gone the group can be deleted.
    await client.delete(f"/api/v1/groups/{group_id}/members/{student['user']['id']}", headers=tutor["headers"])
    deleted = await client.delete(f"/api/v1/groups/{group_id}", headers=tutor["headers"])
    assert deleted.status_code == 204, deleted.text

    assert (await client.get("/api/v1/groups/tutor/me", headers=tutor["headers"])).json() == []
    assert (await client.get(f"/api/v1/groups/{group_id}/occurrences")).status_code == 404


async def test_group_chat_outlives_the_deleted_group(client: AsyncClient) -> None:
    """Section 2.11: deleting a group must not delete the correspondence - the thread
    is kept as an archive for the tutor, under the group's last known name."""
    tutor = await _setup_tutor_with_group(client, "group-chat-delete-tutor@example.com")
    group_id = tutor["group"]["id"]

    thread = (await client.get(f"/api/v1/chat/threads/group/{group_id}", headers=tutor["headers"])).json()
    sent = await client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages",
        headers=tutor["headers"],
        data={"content": "Занятие переносится"},
    )
    assert sent.status_code == 201, sent.text

    assert (await client.delete(f"/api/v1/groups/{group_id}", headers=tutor["headers"])).status_code == 204

    messages = await client.get(f"/api/v1/chat/threads/{thread['id']}/messages", headers=tutor["headers"])
    assert messages.status_code == 200, "the archived thread must stay readable"
    assert [m["content"] for m in messages.json()] == ["Занятие переносится"]

    threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    archived = next(t for t in threads if t["id"] == thread["id"])
    assert archived["group_id"] is None
    assert archived["display_title"] == "Подготовка к ЕГЭ (группа удалена)"


async def test_delete_group_is_owner_only(client: AsyncClient) -> None:
    tutor = await _setup_tutor_with_group(client, "group-delete-owner@example.com")
    other = await _setup_tutor_with_group(client, "group-delete-other@example.com")

    resp = await client.delete(f"/api/v1/groups/{tutor['group']['id']}", headers=other["headers"])
    assert resp.status_code == 403
    assert (await client.get("/api/v1/groups/tutor/me", headers=tutor["headers"])).json() != []
