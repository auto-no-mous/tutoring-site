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
            "student_id": student["user"]["id"],
            "content_url": "https://example.com/variant1.pdf",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    assignment = create_resp.json()
    assert assignment["content_type"] == "link"

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
        data={"title": "ДЗ №1", "submission_mode": "file_upload", "group_id": group_id},
        files={"file": ("task.pdf", file_bytes, "application/pdf")},
    )
    assert create_resp.status_code == 201, create_resp.text
    assignment = create_resp.json()
    assert assignment["content_type"] == "file"
    assert assignment["content_file_path"].startswith("/files/homework/")

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
            "student_id": student["user"]["id"],
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
        data={"title": "ДЗ2", "submission_mode": "file_upload", "student_id": student["user"]["id"]},
        files={"file": ("task.pdf", b"data", "application/pdf")},
    )
    assert file_upload_resp.status_code == 201
    submission_id2 = [
        h for h in (await client.get("/api/v1/homework/me", headers=student["headers"])).json()
        if h["assignment_id"] == file_upload_resp.json()["id"]
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
        data={"title": "ДЗ", "submission_mode": "mark_done", "student_id": student["user"]["id"]},
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
            "student_id": student["user"]["id"],
            "content_url": "https://example.com/x",
        },
    )
    assignment_id = create_resp.json()["id"]
    assert len((await client.get("/api/v1/homework/me", headers=student["headers"])).json()) == 1

    delete_resp = await client.delete(f"/api/v1/homework/{assignment_id}", headers=tutor["headers"])
    assert delete_resp.status_code == 204
    assert (await client.get("/api/v1/homework/me", headers=student["headers"])).json() == []


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
            "student_id": student["user"]["id"],
            "content_url": "https://example.com/x",
        },
    )
    assignment_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/homework/{assignment_id}", headers=tutor_b["headers"])
    assert resp.status_code == 403
