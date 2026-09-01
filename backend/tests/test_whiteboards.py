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
    return {
        "user": body["user"],
        "headers": {"Authorization": f"Bearer {body['tokens']['access_token']}"},
    }


async def _group(client: AsyncClient, tutor: dict, name: str = "Группа") -> str:
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Группа", "format": "group", "duration_minutes": 90, "price": 500},
        )
    ).json()["id"]
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


async def test_student_sees_only_own_boards(client: AsyncClient) -> None:
    tutor = await _register(client, "wb-tutor1@example.com", "tutor")
    student = await _register(client, "wb-student1@example.com", "student")
    stranger = await _register(client, "wb-student2@example.com", "student")

    resp = await client.post(
        "/api/v1/whiteboards",
        headers=tutor["headers"],
        json={"student_id": student["user"]["id"], "url": "https://miro.com/app/board/1", "title": "Алгебра"},
    )
    assert resp.status_code == 201, resp.text
    board = resp.json()
    assert board["title"] == "Алгебра"

    mine = (await client.get("/api/v1/whiteboards/my", headers=student["headers"])).json()
    assert [b["id"] for b in mine] == [board["id"]]

    # Доска пары не видна постороннему ученику - даже того же репетитора.
    other = (await client.get("/api/v1/whiteboards/my", headers=stranger["headers"])).json()
    assert other == []


async def test_group_board_visible_to_members_only(client: AsyncClient) -> None:
    tutor = await _register(client, "wb-tutor2@example.com", "tutor")
    member = await _register(client, "wb-member@example.com", "student")
    outsider = await _register(client, "wb-outsider@example.com", "student")
    group_id = await _group(client, tutor, "Подготовка к ЕГЭ")

    application = await client.post(
        f"/api/v1/groups/{group_id}/apply", headers=member["headers"], json={}
    )
    await client.post(
        f"/api/v1/groups/{group_id}/applications/{application.json()['id']}/accept",
        headers=tutor["headers"],
    )

    resp = await client.post(
        "/api/v1/whiteboards",
        headers=tutor["headers"],
        json={"group_id": group_id, "url": "https://excalidraw.com/#room=abc"},
    )
    assert resp.status_code == 201, resp.text

    assert len((await client.get("/api/v1/whiteboards/my", headers=member["headers"])).json()) == 1
    assert (await client.get("/api/v1/whiteboards/my", headers=outsider["headers"])).json() == []


async def test_last_opened_board_comes_first(client: AsyncClient) -> None:
    """Карточка занятия показывает последнюю открытую доску - значит порядок должен
    меняться от того, что открывали, а не от того, что заводили раньше."""
    tutor = await _register(client, "wb-tutor3@example.com", "tutor")
    student = await _register(client, "wb-student3@example.com", "student")

    first = (
        await client.post(
            "/api/v1/whiteboards",
            headers=tutor["headers"],
            json={"student_id": student["user"]["id"], "url": "https://miro.com/app/board/1"},
        )
    ).json()
    second = (
        await client.post(
            "/api/v1/whiteboards",
            headers=tutor["headers"],
            json={"student_id": student["user"]["id"], "url": "https://miro.com/app/board/2"},
        )
    ).json()

    boards = (await client.get("/api/v1/whiteboards/my", headers=tutor["headers"])).json()
    assert [b["id"] for b in boards] == [second["id"], first["id"]]

    # Открыть доску может и ученик: «последняя открытая» - про общую работу пары.
    resp = await client.post(f"/api/v1/whiteboards/{first['id']}/use", headers=student["headers"])
    assert resp.status_code == 200, resp.text

    boards = (await client.get("/api/v1/whiteboards/my", headers=tutor["headers"])).json()
    assert [b["id"] for b in boards] == [first["id"], second["id"]]


async def test_only_owning_tutor_manages_boards(client: AsyncClient) -> None:
    tutor = await _register(client, "wb-tutor4@example.com", "tutor")
    stranger = await _register(client, "wb-tutor5@example.com", "tutor")
    student = await _register(client, "wb-student4@example.com", "student")

    board = (
        await client.post(
            "/api/v1/whiteboards",
            headers=tutor["headers"],
            json={"student_id": student["user"]["id"], "url": "https://miro.com/app/board/1"},
        )
    ).json()

    # Чужой репетитор не правит и не удаляет.
    assert (
        await client.patch(
            f"/api/v1/whiteboards/{board['id']}",
            headers=stranger["headers"],
            json={"title": "Моя"},
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/whiteboards/{board['id']}", headers=stranger["headers"])
    ).status_code == 404

    # Ученик видит доску, но заводить и удалять не может - список ведёт репетитор.
    assert (
        await client.post(
            "/api/v1/whiteboards",
            headers=student["headers"],
            json={"student_id": student["user"]["id"], "url": "https://miro.com/app/board/9"},
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/whiteboards/{board['id']}", headers=student["headers"])
    ).status_code == 403

    resp = await client.patch(
        f"/api/v1/whiteboards/{board['id']}",
        headers=tutor["headers"],
        json={"title": "Геометрия", "url": "https://miro.com/app/board/renamed"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Геометрия"
    assert resp.json()["url"].endswith("/renamed")

    assert (
        await client.delete(f"/api/v1/whiteboards/{board['id']}", headers=tutor["headers"])
    ).status_code == 204
    assert (await client.get("/api/v1/whiteboards/my", headers=tutor["headers"])).json() == []


async def test_board_needs_exactly_one_owner_and_a_safe_url(client: AsyncClient) -> None:
    tutor = await _register(client, "wb-tutor6@example.com", "tutor")
    student = await _register(client, "wb-student6@example.com", "student")
    group_id = await _group(client, tutor)

    # Ни ученика, ни группы.
    assert (
        await client.post(
            "/api/v1/whiteboards", headers=tutor["headers"], json={"url": "https://miro.com/x"}
        )
    ).status_code == 422
    # И ученик, и группа сразу.
    assert (
        await client.post(
            "/api/v1/whiteboards",
            headers=tutor["headers"],
            json={
                "student_id": student["user"]["id"],
                "group_id": group_id,
                "url": "https://miro.com/x",
            },
        )
    ).status_code == 422
    # Ссылка попадает в <a href> - javascript: там быть не должно.
    assert (
        await client.post(
            "/api/v1/whiteboards",
            headers=tutor["headers"],
            json={"student_id": student["user"]["id"], "url": "javascript:alert(1)"},
        )
    ).status_code == 422
