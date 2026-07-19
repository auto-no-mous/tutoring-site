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


async def test_individual_chat_flow_and_isolation(client: AsyncClient) -> None:
    tutor = await _register(client, "chat-tutor1@example.com", "tutor")
    student = await _register(client, "chat-student1@example.com", "student")
    outsider = await _register(client, "chat-outsider1@example.com", "student")

    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    open_resp = await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student["headers"])
    assert open_resp.status_code == 200, open_resp.text
    thread_id = open_resp.json()["id"]
    assert open_resp.json()["display_title"] == "tutor Test"

    # Opening from the tutor side with the same counterpart returns the same thread.
    open_resp2 = await client.post(
        f"/api/v1/chat/threads/with-student/{student['user']['id']}", headers=tutor["headers"]
    )
    assert open_resp2.json()["id"] == thread_id
    assert open_resp2.json()["display_title"] == "student Test"

    send1 = await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], data={"content": "Здравствуйте!"}
    )
    assert send1.status_code == 201, send1.text
    send2 = await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=tutor["headers"], data={"content": "Добрый день"}
    )
    assert send2.status_code == 201

    messages = (await client.get(f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"])).json()
    assert [m["content"] for m in messages] == ["Здравствуйте!", "Добрый день"]

    # A third party has no access.
    forbidden_list = await client.get(f"/api/v1/chat/threads/{thread_id}/messages", headers=outsider["headers"])
    assert forbidden_list.status_code == 403
    forbidden_send = await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=outsider["headers"], data={"content": "hi"}
    )
    assert forbidden_send.status_code == 403

    tutor_threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    assert any(t["id"] == thread_id for t in tutor_threads)
    student_threads = (await client.get("/api/v1/chat/threads", headers=student["headers"])).json()
    assert any(t["id"] == thread_id for t in student_threads)


async def test_group_chat_created_with_group_and_membership_gated(client: AsyncClient) -> None:
    tutor = await _register(client, "chat-tutor2@example.com", "tutor")
    lesson_type_resp = await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=tutor["headers"],
        json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
    )
    group_resp = await client.post(
        "/api/v1/groups",
        headers=tutor["headers"],
        json={
            "name": "Группа чата",
            "lesson_type_id": lesson_type_resp.json()["id"],
            "capacity": 2,
            "schedule_slots": [{"weekday": 1, "start_time": "18:00:00"}],
        },
    )
    group_id = group_resp.json()["id"]

    member = await _register(client, "chat-member@example.com", "student")
    not_member = await _register(client, "chat-notmember@example.com", "student")

    thread_resp = await client.get(f"/api/v1/chat/threads/group/{group_id}", headers=tutor["headers"])
    assert thread_resp.status_code == 200, thread_resp.text
    thread_id = thread_resp.json()["id"]
    assert thread_resp.json()["display_title"] == "Группа чата"

    # Not yet a member: no access.
    denied = await client.get(f"/api/v1/chat/threads/group/{group_id}", headers=member["headers"])
    assert denied.status_code == 403

    app_resp = await client.post(f"/api/v1/groups/{group_id}/apply", headers=member["headers"], json={})
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{app_resp.json()['id']}/accept", headers=tutor["headers"]
    )

    now_allowed = await client.get(f"/api/v1/chat/threads/group/{group_id}", headers=member["headers"])
    assert now_allowed.status_code == 200

    send_resp = await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=member["headers"], data={"content": "Привет всем"}
    )
    assert send_resp.status_code == 201

    still_denied = await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=not_member["headers"], data={"content": "hi"}
    )
    assert still_denied.status_code == 403

    # Leaving the group revokes access again.
    await client.post(f"/api/v1/groups/{group_id}/leave", headers=member["headers"])
    revoked = await client.get(f"/api/v1/chat/threads/{thread_id}/messages", headers=member["headers"])
    assert revoked.status_code == 403


async def test_empty_message_rejected(client: AsyncClient) -> None:
    tutor = await _register(client, "chat-tutor3@example.com", "tutor")
    student = await _register(client, "chat-student3@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    thread_id = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student["headers"])
    ).json()["id"]

    resp = await client.post(f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], data={})
    assert resp.status_code == 422
