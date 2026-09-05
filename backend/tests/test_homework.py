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


async def test_individual_homework_link_mark_done(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor1@example.com", "tutor")
    student = await _register(client, "hw-student1@example.com", "student")

    create_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "Вариант ЕГЭ №1",
            "submission_mode": "mark_done",
            "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/variant1.pdf",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert len(created) == 1
    assignment = created[0]
    assert assignment["content_type"] == "link"
    assert assignment["student_display_name"] == student["user"]["display_name"]
    assert assignment["status"] == "pending"

    my_hw = (await client.get("/api/v1/homework/me", headers=student["headers"])).json()
    assert len(my_hw) == 1
    assert my_hw[0]["status"] == "pending"
    submission_id = my_hw[0]["submission_id"]

    done_resp = await client.post(f"/api/v1/homework/submissions/{submission_id}/done", headers=student["headers"])
    assert done_resp.status_code == 200, done_resp.text
    assert done_resp.json()["status"] == "done"
    assert done_resp.json()["submitted_at"] is not None


async def test_group_homework_assigned_to_all_active_members(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor2@example.com", "tutor")
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
    )
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Группа A",
            "lesson_type_id": lesson_type_resp.json()["id"],
            "capacity": 5,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]

    student1 = await _register(client, "hw-student2a@example.com", "student")
    student2 = await _register(client, "hw-student2b@example.com", "student")
    # A third student applies but is never accepted - should not receive the homework.
    student3 = await _register(client, "hw-student2c@example.com", "student")
    await client.post(f"/api/v1/groups/{group_id}/apply", headers=student3["headers"], json={})

    for student in (student1, student2):
        app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=student["headers"], json={})
        await client.post(
            f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
        )

    file_bytes = b"homework material content"
    create_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={"title": "ДЗ №1", "submission_mode": "file_upload", "group_ids": [group_id]},
        files={"file": ("task.pdf", file_bytes, "application/pdf")},
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert len(created) == 1
    assignment = created[0]
    assert assignment["content_type"] == "file"
    assert assignment["content_file_path"].startswith("/files/homework/")
    assert assignment["group_name"] == "Группа A"

    student1_hw = (await client.get("/api/v1/homework/me", headers=student1["headers"])).json()
    student2_hw = (await client.get("/api/v1/homework/me", headers=student2["headers"])).json()
    student3_hw = (await client.get("/api/v1/homework/me", headers=student3["headers"])).json()
    assert len(student1_hw) == 1
    assert len(student2_hw) == 1
    assert student3_hw == []

    submission_id = student1_hw[0]["submission_id"]
    upload_resp = await client.post(
        f"/api/v1/homework/submissions/{submission_id}/upload",
        headers=student1["headers"],
        data={"comment": "готово"},
        files={"file": ("answer.pdf", b"my answer", "application/pdf")},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    assert upload_resp.json()["status"] == "submitted"
    assert upload_resp.json()["file_path"].startswith("/files/homework-submissions/")

    assert assignment["status"] == "pending"
    submissions = (
        await client.get(f"/api/v1/homework/{assignment['id']}/submissions", headers=tutor["headers"])
    ).json()
    assert len(submissions) == 2
    statuses = {s["student_id"]: s["status"] for s in submissions}
    assert statuses[student1["user"]["id"]] == "submitted"
    assert statuses[student2["user"]["id"]] == "pending"


async def test_wrong_submission_action_rejected(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor3@example.com", "tutor")
    student = await _register(client, "hw-student3@example.com", "student")

    mark_done_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "ДЗ",
            "submission_mode": "mark_done",
            "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/x",
        },
    )
    submission_id = (await client.get("/api/v1/homework/me", headers=student["headers"])).json()[0]["submission_id"]
    assert mark_done_resp.status_code == 201

    upload_resp = await client.post(
        f"/api/v1/homework/submissions/{submission_id}/upload",
        headers=student["headers"],
        files={"file": ("x.pdf", b"data", "application/pdf")},
    )
    assert upload_resp.status_code == 409

    file_upload_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={"title": "ДЗ2", "submission_mode": "file_upload", "student_ids": [student["user"]["id"]]},
        files={"file": ("task.pdf", b"data", "application/pdf")},
    )
    assert file_upload_resp.status_code == 201
    file_assignment_id = file_upload_resp.json()[0]["id"]
    submission_id2 = [
        h for h in (await client.get("/api/v1/homework/me", headers=student["headers"])).json()
        if h["assignment_id"] == file_assignment_id
    ][0]["submission_id"]

    mark_done_wrong = await client.post(
        f"/api/v1/homework/submissions/{submission_id2}/done", headers=student["headers"]
    )
    assert mark_done_wrong.status_code == 409


async def test_content_and_target_validation(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor4@example.com", "tutor")
    student = await _register(client, "hw-student4@example.com", "student")

    neither_target = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={"title": "ДЗ", "submission_mode": "mark_done", "content_url": "https://example.com/x"},
    )
    assert neither_target.status_code == 422

    neither_content = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={"title": "ДЗ", "submission_mode": "mark_done", "student_ids": [student["user"]["id"]]},
    )
    assert neither_content.status_code == 422


async def test_tutor_deletes_assignment_cascades_submissions(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor5@example.com", "tutor")
    student = await _register(client, "hw-student5@example.com", "student")

    create_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "ДЗ",
            "submission_mode": "mark_done",
            "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/x",
        },
    )
    assignment_id = create_resp.json()[0]["id"]
    assert len((await client.get("/api/v1/homework/me", headers=student["headers"])).json()) == 1

    delete_resp = await client.delete(f"/api/v1/homework/{assignment_id}", headers=tutor["headers"])
    assert delete_resp.status_code == 204
    assert (await client.get("/api/v1/homework/me", headers=student["headers"])).json() == []


async def test_student_status_map_and_tutor_scoped_list(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor7@example.com", "tutor")
    other_tutor = await _register(client, "hw-tutor7b@example.com", "tutor")
    student1 = await _register(client, "hw-student7a@example.com", "student")
    student2 = await _register(client, "hw-student7b@example.com", "student")

    # No homework yet - both absent from the map, empty list for each.
    empty_map = (await client.get("/api/v1/homework/tutor/me/student-status", headers=tutor["headers"])).json()
    assert empty_map == {}

    await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "ДЗ 1", "submission_mode": "mark_done", "student_ids": [student1["user"]["id"]],
            "content_url": "https://example.com/1",
        },
    )
    await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "ДЗ 2", "submission_mode": "mark_done", "student_ids": [student2["user"]["id"]],
            "content_url": "https://example.com/2",
        },
    )
    # A homework assignment from a different tutor must not affect student1's status here.
    await client.post(
        "/api/v1/homework",
        headers=other_tutor["headers"],
        data={
            "title": "Другое ДЗ", "submission_mode": "mark_done", "student_ids": [student1["user"]["id"]],
            "content_url": "https://example.com/x",
        },
    )

    status_map = (await client.get("/api/v1/homework/tutor/me/student-status", headers=tutor["headers"])).json()
    assert status_map[student1["user"]["id"]] == "pending"
    assert status_map[student2["user"]["id"]] == "pending"

    # student1 marks their assignment done - status flips to "done" (only one
    # assignment from this tutor, and it's now complete).
    submission_id = [
        h for h in (await client.get("/api/v1/homework/me", headers=student1["headers"])).json()
        if h["tutor_id"] == (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    ][0]["submission_id"]
    await client.post(f"/api/v1/homework/submissions/{submission_id}/done", headers=student1["headers"])

    updated_map = (await client.get("/api/v1/homework/tutor/me/student-status", headers=tutor["headers"])).json()
    assert updated_map[student1["user"]["id"]] == "done"
    assert updated_map[student2["user"]["id"]] == "pending"

    student1_view = (
        await client.get(f"/api/v1/homework/tutor/me/students/{student1['user']['id']}", headers=tutor["headers"])
    ).json()
    assert len(student1_view) == 1  # only this tutor's assignment, not other_tutor's
    assert student1_view[0]["status"] == "done"


async def test_tutor_can_manually_override_submission_status(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor8@example.com", "tutor")
    other_tutor = await _register(client, "hw-tutor8b@example.com", "tutor")
    student = await _register(client, "hw-student8@example.com", "student")

    create_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "Старое ДЗ", "submission_mode": "mark_done", "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/x",
        },
    )
    submission_id = (await client.get("/api/v1/homework/me", headers=student["headers"])).json()[0]["submission_id"]

    # A different tutor may not touch this submission.
    forbidden = await client.patch(
        f"/api/v1/homework/submissions/{submission_id}/status",
        headers=other_tutor["headers"],
        json={"status": "done"},
    )
    assert forbidden.status_code == 403

    invalid = await client.patch(
        f"/api/v1/homework/submissions/{submission_id}/status",
        headers=tutor["headers"],
        json={"status": "not-a-real-status"},
    )
    assert invalid.status_code == 422

    # Tutor closes out a stale pending debt without the student ever submitting.
    override_resp = await client.patch(
        f"/api/v1/homework/submissions/{submission_id}/status",
        headers=tutor["headers"],
        json={"status": "done"},
    )
    assert override_resp.status_code == 200, override_resp.text
    assert override_resp.json()["status"] == "done"
    assert override_resp.json()["submitted_at"] is None  # not fabricated

    assert create_resp.status_code == 201


async def test_tutor_cannot_delete_other_tutors_assignment(client: AsyncClient) -> None:
    tutor_a = await _register(client, "hw-tutorA@example.com", "tutor")
    tutor_b = await _register(client, "hw-tutorB@example.com", "tutor")
    student = await _register(client, "hw-student6@example.com", "student")

    create_resp = await client.post(
        "/api/v1/homework",
        headers=tutor_a["headers"],
        data={
            "title": "ДЗ",
            "submission_mode": "mark_done",
            "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/x",
        },
    )
    assignment_id = create_resp.json()[0]["id"]

    resp = await client.delete(f"/api/v1/homework/{assignment_id}", headers=tutor_b["headers"])
    assert resp.status_code == 403


async def test_no_recipients_rejected(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor9@example.com", "tutor")

    resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={"submission_mode": "mark_done", "content_url": "https://example.com/x"},
    )
    assert resp.status_code == 422


async def test_title_is_optional(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor10@example.com", "tutor")
    student = await _register(client, "hw-student10@example.com", "student")

    resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "submission_mode": "mark_done",
            "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/x",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()[0]["title"] is None

    # Регрессия: список у ученика падал с 500 - в схеме ответа заголовок оставался
    # обязательным, и задание без названия было невозможно показать.
    mine = await client.get("/api/v1/homework/me", headers=student["headers"])
    assert mine.status_code == 200, mine.text
    assert mine.json()[0]["title"] is None


async def test_create_sends_same_homework_to_multiple_students_and_a_group(client: AsyncClient) -> None:
    """Like addressing an email to several recipients at once - one submit creates
    one HomeworkAssignment (and its own submission tracking) per recipient."""
    tutor = await _register(client, "hw-tutor11@example.com", "tutor")
    student1 = await _register(client, "hw-student11a@example.com", "student")
    student2 = await _register(client, "hw-student11b@example.com", "student")

    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
    )
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Группа B",
            "lesson_type_id": lesson_type_resp.json()["id"],
            "capacity": 5,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]
    group_student = await _register(client, "hw-student11c@example.com", "student")
    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=group_student["headers"], json={})
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
    )

    resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "Общее задание",
            "submission_mode": "mark_done",
            "student_ids": [student1["user"]["id"], student2["user"]["id"]],
            "group_ids": [group_id],
            "content_url": "https://example.com/shared",
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    # One assignment per recipient (2 students + 1 group), all sharing the same content.
    assert len(created) == 3
    assert all(a["content_url"] == "https://example.com/shared" for a in created)
    assert {a["student_display_name"] for a in created if a["student_id"]} == {
        student1["user"]["display_name"], student2["user"]["display_name"],
    }
    assert [a["group_name"] for a in created if a["group_id"]] == ["Группа B"]

    all_assignments = (await client.get("/api/v1/homework/tutor/me", headers=tutor["headers"])).json()
    assert len(all_assignments) == 3


async def test_update_assignment_title_and_content(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor12@example.com", "tutor")
    other_tutor = await _register(client, "hw-tutor12b@example.com", "tutor")
    student = await _register(client, "hw-student12@example.com", "student")

    create_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "Черновик",
            "submission_mode": "mark_done",
            "student_ids": [student["user"]["id"]],
            "content_url": "https://example.com/old",
        },
    )
    assignment_id = create_resp.json()[0]["id"]

    forbidden = await client.patch(
        f"/api/v1/homework/{assignment_id}",
        headers=other_tutor["headers"],
        data={"title": "Хак", "submission_mode": "mark_done", "content_url": "https://example.com/hack"},
    )
    assert forbidden.status_code == 403

    update_resp = await client.patch(
        f"/api/v1/homework/{assignment_id}",
        headers=tutor["headers"],
        data={"title": "Готово", "submission_mode": "file_upload", "content_url": "https://example.com/new"},
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["title"] == "Готово"
    assert updated["submission_mode"] == "file_upload"
    assert updated["content_url"] == "https://example.com/new"

    # Omitting content entirely keeps the existing material untouched (edit form's
    # "Заменить материал" left unchecked) rather than erroring.
    keep_content = await client.patch(
        f"/api/v1/homework/{assignment_id}",
        headers=tutor["headers"],
        data={"title": "Не трогаем материал", "submission_mode": "mark_done"},
    )
    assert keep_content.status_code == 200, keep_content.text
    assert keep_content.json()["content_url"] == "https://example.com/new"
    assert keep_content.json()["content_type"] == "link"


async def test_duplicate_assignment_reuses_content_for_new_recipients(client: AsyncClient) -> None:
    tutor = await _register(client, "hw-tutor13@example.com", "tutor")
    other_tutor = await _register(client, "hw-tutor13b@example.com", "tutor")
    student1 = await _register(client, "hw-student13a@example.com", "student")
    student2 = await _register(client, "hw-student13b@example.com", "student")

    file_bytes = b"original material"
    create_resp = await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "Оригинал",
            "submission_mode": "file_upload",
            "student_ids": [student1["user"]["id"]],
        },
        files={"file": ("task.pdf", file_bytes, "application/pdf")},
    )
    assignment_id = create_resp.json()[0]["id"]
    original_file_path = create_resp.json()[0]["content_file_path"]

    forbidden = await client.post(
        f"/api/v1/homework/{assignment_id}/duplicate",
        headers=other_tutor["headers"],
        data={"student_ids": [student2["user"]["id"]]},
    )
    assert forbidden.status_code == 403

    no_recipients = await client.post(
        f"/api/v1/homework/{assignment_id}/duplicate", headers=tutor["headers"], data={}
    )
    assert no_recipients.status_code == 422

    dup_resp = await client.post(
        f"/api/v1/homework/{assignment_id}/duplicate",
        headers=tutor["headers"],
        data={"student_ids": [student2["user"]["id"]]},
    )
    assert dup_resp.status_code == 201, dup_resp.text
    duplicated = dup_resp.json()
    assert len(duplicated) == 1
    assert duplicated[0]["id"] != assignment_id
    assert duplicated[0]["title"] == "Оригинал"
    assert duplicated[0]["content_file_path"] == original_file_path  # no re-upload needed
    assert duplicated[0]["student_display_name"] == student2["user"]["display_name"]

    # The original recipient's assignment is untouched; the new recipient now has one too.
    student1_hw = (await client.get("/api/v1/homework/me", headers=student1["headers"])).json()
    student2_hw = (await client.get("/api/v1/homework/me", headers=student2["headers"])).json()
    assert len(student1_hw) == 1
    assert len(student2_hw) == 1
