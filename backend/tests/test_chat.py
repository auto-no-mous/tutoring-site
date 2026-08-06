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
    assert send1.json()["sender_display_name"] == "student Test"
    assert send2.json()["sender_display_name"] == "tutor Test"
    assert [m["sender_display_name"] for m in messages] == ["student Test", "tutor Test"]

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


async def test_unread_count_and_last_message_preview(client: AsyncClient) -> None:
    tutor = await _register(client, "chat-tutor4@example.com", "tutor")
    student = await _register(client, "chat-student4@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    thread_id = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student["headers"])
    ).json()["id"]

    # No messages yet: both sides see zero unread and no preview.
    tutor_threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    thread = next(t for t in tutor_threads if t["id"] == thread_id)
    assert thread["unread_count"] == 0
    assert thread["last_message_preview"] is None

    await client.post(
        f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], data={"content": "Здравствуйте!"}
    )

    # The tutor has one unread message from the student; the student's own view
    # shows zero unread (they sent it themselves) and the same preview text.
    tutor_threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    thread = next(t for t in tutor_threads if t["id"] == thread_id)
    assert thread["unread_count"] == 1
    assert thread["last_message_preview"] == "Здравствуйте!"
    assert thread["last_message_at"] is not None

    student_threads = (await client.get("/api/v1/chat/threads", headers=student["headers"])).json()
    student_view = next(t for t in student_threads if t["id"] == thread_id)
    assert student_view["unread_count"] == 0
    assert student_view["last_message_preview"] == "Здравствуйте!"

    # Fetching messages marks the thread as read.
    await client.get(f"/api/v1/chat/threads/{thread_id}/messages", headers=tutor["headers"])
    tutor_threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    thread = next(t for t in tutor_threads if t["id"] == thread_id)
    assert thread["unread_count"] == 0

    # A file-only message (no text content) gets a generic preview.
    files = {"file": ("note.txt", b"hello", "text/plain")}
    await client.post(f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], files=files)
    tutor_threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    thread = next(t for t in tutor_threads if t["id"] == thread_id)
    assert thread["unread_count"] == 1
    assert thread["last_message_preview"] == "📎 Файл"


async def test_threads_sorted_by_most_recent_activity(client: AsyncClient) -> None:
    tutor = await _register(client, "chat-tutor5@example.com", "tutor")
    student_a = await _register(client, "chat-student5a@example.com", "student")
    student_b = await _register(client, "chat-student5b@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    thread_a = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student_a["headers"])
    ).json()["id"]
    thread_b = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student_b["headers"])
    ).json()["id"]

    # Message thread A first, then B - B should now sort above A.
    await client.post(f"/api/v1/chat/threads/{thread_a}/messages", headers=student_a["headers"], data={"content": "A"})
    await client.post(f"/api/v1/chat/threads/{thread_b}/messages", headers=student_b["headers"], data={"content": "B"})

    tutor_threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    ids_in_order = [t["id"] for t in tutor_threads if t["id"] in (thread_a, thread_b)]
    assert ids_in_order == [thread_b, thread_a]

    # Messaging A again brings it back to the top.
    await client.post(f"/api/v1/chat/threads/{thread_a}/messages", headers=student_a["headers"], data={"content": "A again"})
    tutor_threads = (await client.get("/api/v1/chat/threads", headers=tutor["headers"])).json()
    ids_in_order = [t["id"] for t in tutor_threads if t["id"] in (thread_a, thread_b)]
    assert ids_in_order == [thread_a, thread_b]


async def test_list_threads_survives_mix_of_empty_and_active_threads(client: AsyncClient) -> None:
    """Regression test: a real account had a thread with messages and a thread with
    none (e.g. a freshly opened chat, or a group nobody has messaged yet) - sorting
    by last_message_at used to crash comparing a naive datetime (read straight off a
    SQLite row via model_copy, which skips the UTCDateTime validator) against the
    timezone-aware "no messages" fallback, making GET /chat/threads 500 and the
    thread list look empty, even though the threads themselves still existed and
    were individually reachable (e.g. via GET /chat/threads/group/{id})."""
    tutor = await _register(client, "chat-tutor6@example.com", "tutor")
    student_with_messages = await _register(client, "chat-student6a@example.com", "student")
    student_no_messages = await _register(client, "chat-student6b@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]

    thread_with_messages = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student_with_messages["headers"])
    ).json()["id"]
    thread_no_messages = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student_no_messages["headers"])
    ).json()["id"]

    await client.post(
        f"/api/v1/chat/threads/{thread_with_messages}/messages",
        headers=student_with_messages["headers"],
        data={"content": "Hello"},
    )

    tutor_threads_resp = await client.get("/api/v1/chat/threads", headers=tutor["headers"])
    assert tutor_threads_resp.status_code == 200, tutor_threads_resp.text
    tutor_threads = tutor_threads_resp.json()
    ids_in_order = [t["id"] for t in tutor_threads if t["id"] in (thread_with_messages, thread_no_messages)]
    assert ids_in_order == [thread_with_messages, thread_no_messages]
    empty_thread = next(t for t in tutor_threads if t["id"] == thread_no_messages)
    assert empty_thread["last_message_at"] is None
    assert empty_thread["last_message_preview"] is None

    student_no_messages_resp = await client.get("/api/v1/chat/threads", headers=student_no_messages["headers"])
    assert student_no_messages_resp.status_code == 200, student_no_messages_resp.text


async def test_messageable_students_excludes_already_threaded(client: AsyncClient) -> None:
    """GET /chat/students powers "Новый чат" - it must only offer booked students who
    don't already have an individual thread (once a thread exists, the tutor reaches
    that student through the ordinary thread list instead, see components/ChatPanel.vue)."""
    tutor = await _register(client, "chat-tutor7@example.com", "tutor")
    fresh_student = await _register(client, "chat-student7a@example.com", "student")
    already_threaded_student = await _register(client, "chat-student7b@example.com", "student")
    unrelated_student = await _register(client, "chat-student7c@example.com", "student")

    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5)
    end = start + dt.timedelta(minutes=60)
    for student in (fresh_student, already_threaded_student):
        booking_resp = await client.post(
            "/api/v1/bookings/manual",
            headers=tutor["headers"],
            json={"student_id": student["user"]["id"], "start_at": start.isoformat(), "end_at": end.isoformat()},
        )
        assert booking_resp.status_code == 201, booking_resp.text
        start += dt.timedelta(hours=2)
        end += dt.timedelta(hours=2)

    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=already_threaded_student["headers"])

    resp = await client.get("/api/v1/chat/students", headers=tutor["headers"])
    assert resp.status_code == 200, resp.text
    ids = {s["id"] for s in resp.json()}
    assert fresh_student["user"]["id"] in ids
    assert already_threaded_student["user"]["id"] not in ids
    assert unrelated_student["user"]["id"] not in ids

    denied = await client.get("/api/v1/chat/students", headers=fresh_student["headers"])
    assert denied.status_code == 403


async def test_empty_message_rejected(client: AsyncClient) -> None:
    tutor = await _register(client, "chat-tutor3@example.com", "tutor")
    student = await _register(client, "chat-student3@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    thread_id = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student["headers"])
    ).json()["id"]

    resp = await client.post(f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], data={})
    assert resp.status_code == 422


async def test_attachment_upload_rejects_disallowed_content_type(client: AsyncClient) -> None:
    """Regression test: chat/homework uploads used to have no content-type
    restriction at all, meaning an .html attachment would be stored and served
    same-origin as the SPA (stored XSS) - see file_service.save_upload."""
    tutor = await _register(client, "chat-tutor8@example.com", "tutor")
    student = await _register(client, "chat-student8@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    thread_id = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student["headers"])
    ).json()["id"]

    files = {"file": ("xss.html", b"<script>alert(1)</script>", "text/html")}
    resp = await client.post(f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], files=files)
    assert resp.status_code == 400


async def test_attachment_upload_ignores_client_supplied_extension(client: AsyncClient) -> None:
    """Regression test: the stored file's extension used to come straight from the
    client-supplied filename, so a request claiming an allowed content-type (e.g.
    text/plain) with a filename like xss.html would still get stored AND SERVED as
    .html - see file_service._CONTENT_TYPE_EXTENSIONS. The extension must instead be
    derived from the validated content-type, never the filename."""
    tutor = await _register(client, "chat-tutor9@example.com", "tutor")
    student = await _register(client, "chat-student9@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    thread_id = (
        await client.post(f"/api/v1/chat/threads/with-tutor/{tutor_id}", headers=student["headers"])
    ).json()["id"]

    files = {"file": ("xss.html", b"<script>alert(1)</script>", "text/plain")}
    resp = await client.post(f"/api/v1/chat/threads/{thread_id}/messages", headers=student["headers"], files=files)
    assert resp.status_code == 201, resp.text
    file_path = resp.json()["file_path"]
    assert file_path.endswith(".txt")
    assert not file_path.endswith(".html")
