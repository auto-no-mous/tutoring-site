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


async def _admin_headers(client: AsyncClient, db_session: AsyncSession, email: str = "subj-admin@example.com") -> dict:
    admin = User(
        role="admin",
        email=email,
        password_hash=hash_password("adminpass1"),
        first_name="Admin",
        last_name="Admin",
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


async def test_admin_subject_and_direction_crud(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session)

    create_resp = await client.post("/api/v1/admin/subjects", headers=admin_headers, json={"name": "Математика"})
    assert create_resp.status_code == 201, create_resp.text
    subject_id = create_resp.json()["id"]

    dup_resp = await client.post("/api/v1/admin/subjects", headers=admin_headers, json={"name": "Математика"})
    assert dup_resp.status_code == 409

    direction_resp = await client.post(
        f"/api/v1/admin/subjects/{subject_id}/directions", headers=admin_headers, json={"name": "Подготовка к ЕГЭ"}
    )
    assert direction_resp.status_code == 201, direction_resp.text
    direction_id = direction_resp.json()["id"]

    dup_direction = await client.post(
        f"/api/v1/admin/subjects/{subject_id}/directions", headers=admin_headers, json={"name": "Подготовка к ЕГЭ"}
    )
    assert dup_direction.status_code == 409

    public_list = await client.get("/api/v1/subjects")
    assert public_list.status_code == 200
    subject = next(s for s in public_list.json() if s["id"] == subject_id)
    assert subject["directions"][0]["name"] == "Подготовка к ЕГЭ"

    rename_resp = await client.patch(
        f"/api/v1/admin/directions/{direction_id}", headers=admin_headers, json={"name": "ЕГЭ"}
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["name"] == "ЕГЭ"

    delete_direction_resp = await client.delete(f"/api/v1/admin/directions/{direction_id}", headers=admin_headers)
    assert delete_direction_resp.status_code == 204

    delete_subject_resp = await client.delete(f"/api/v1/admin/subjects/{subject_id}", headers=admin_headers)
    assert delete_subject_resp.status_code == 204

    final_list = await client.get("/api/v1/subjects")
    assert all(s["id"] != subject_id for s in final_list.json())


async def _seed_subjects(client: AsyncClient, admin_headers: dict) -> dict:
    math_resp = await client.post("/api/v1/admin/subjects", headers=admin_headers, json={"name": "Математика"})
    math_id = math_resp.json()["id"]
    ege_resp = await client.post(
        f"/api/v1/admin/subjects/{math_id}/directions", headers=admin_headers, json={"name": "Подготовка к ЕГЭ"}
    )
    oge_resp = await client.post(
        f"/api/v1/admin/subjects/{math_id}/directions", headers=admin_headers, json={"name": "Подготовка к ОГЭ"}
    )

    music_resp = await client.post("/api/v1/admin/subjects", headers=admin_headers, json={"name": "Музыка"})
    music_id = music_resp.json()["id"]
    solfege_resp = await client.post(
        f"/api/v1/admin/subjects/{music_id}/directions", headers=admin_headers, json={"name": "Сольфеджио"}
    )

    return {
        "math_id": math_id,
        "ege_id": ege_resp.json()["id"],
        "oge_id": oge_resp.json()["id"],
        "music_id": music_id,
        "solfege_id": solfege_resp.json()["id"],
    }


async def test_tutor_subject_assignment_validates_direction_belongs_to_subject(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_headers = await _admin_headers(client, db_session, "subj-admin2@example.com")
    ids = await _seed_subjects(client, admin_headers)
    tutor = await _register(client, "subj-tutor1@example.com", "tutor")

    # A direction from a different subject must be rejected.
    invalid_resp = await client.put(
        "/api/v1/tutors/me/subjects",
        headers=tutor["headers"],
        json={"selections": [{"subject_id": ids["math_id"], "direction_ids": [ids["solfege_id"]]}]},
    )
    assert invalid_resp.status_code == 422

    valid_resp = await client.put(
        "/api/v1/tutors/me/subjects",
        headers=tutor["headers"],
        json={
            "selections": [
                {"subject_id": ids["math_id"], "direction_ids": [ids["ege_id"], ids["oge_id"]]},
                {"subject_id": ids["music_id"], "direction_ids": [ids["solfege_id"]]},
            ]
        },
    )
    assert valid_resp.status_code == 200, valid_resp.text
    body = valid_resp.json()
    assert len(body) == 2
    math_entry = next(s for s in body if s["subject_id"] == ids["math_id"])
    assert {d["id"] for d in math_entry["directions"]} == {ids["ege_id"], ids["oge_id"]}

    get_resp = await client.get("/api/v1/tutors/me/subjects", headers=tutor["headers"])
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 2

    # Replacing again fully overwrites the previous selection.
    replace_resp = await client.put(
        "/api/v1/tutors/me/subjects",
        headers=tutor["headers"],
        json={"selections": [{"subject_id": ids["music_id"], "direction_ids": []}]},
    )
    assert replace_resp.status_code == 200
    assert len(replace_resp.json()) == 1
    assert replace_resp.json()[0]["subject_id"] == ids["music_id"]
    assert replace_resp.json()[0]["directions"] == []


async def test_catalog_filters_by_subject_and_normalizes_hourly_price(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_headers = await _admin_headers(client, db_session, "subj-admin3@example.com")
    ids = await _seed_subjects(client, admin_headers)

    math_tutor = await _register(client, "subj-tutor2@example.com", "tutor")
    await client.put(
        "/api/v1/tutors/me/subjects",
        headers=math_tutor["headers"],
        json={"selections": [{"subject_id": ids["math_id"], "direction_ids": [ids["ege_id"]]}]},
    )
    # 45-minute lesson at 1500 - hourly-normalized that's 2000 (1500 / 45 * 60).
    await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=math_tutor["headers"],
        json={"name": "Занятие", "format": "individual", "duration_minutes": 45, "price": 1500},
    )
    math_tutor_id = (await client.get("/api/v1/tutors/me", headers=math_tutor["headers"])).json()["id"]

    music_tutor = await _register(client, "subj-tutor3@example.com", "tutor")
    await client.put(
        "/api/v1/tutors/me/subjects",
        headers=music_tutor["headers"],
        json={"selections": [{"subject_id": ids["music_id"], "direction_ids": [ids["solfege_id"]]}]},
    )
    await client.post(
        "/api/v1/tutors/me/lesson-types",
        headers=music_tutor["headers"],
        json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
    )
    music_tutor_id = (await client.get("/api/v1/tutors/me", headers=music_tutor["headers"])).json()["id"]

    by_subject = await client.get("/api/v1/tutors", params={"subject_id": ids["math_id"]})
    assert by_subject.status_code == 200
    ids_in_result = {t["id"] for t in by_subject.json()["items"]}
    assert math_tutor_id in ids_in_result
    assert music_tutor_id not in ids_in_result

    math_item = next(t for t in by_subject.json()["items"] if t["id"] == math_tutor_id)
    assert math_item["hourly_price"] == 2000.0
    assert math_item["subjects"] == ["Математика"]

    price_filtered = await client.get("/api/v1/tutors", params={"price_min": 1900, "price_max": 2100})
    price_filtered_ids = {t["id"] for t in price_filtered.json()["items"]}
    assert math_tutor_id in price_filtered_ids
    assert music_tutor_id not in price_filtered_ids


async def test_public_subjects_count_only_visible_tutors(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, "subj-admin4@example.com")
    ids = await _seed_subjects(client, admin_headers)

    visible = await _register(client, "subj-tutor4@example.com", "tutor")
    await client.put(
        "/api/v1/tutors/me/subjects",
        headers=visible["headers"],
        json={"selections": [{"subject_id": ids["math_id"], "direction_ids": [ids["ege_id"], ids["oge_id"]]}]},
    )

    hidden = await _register(client, "subj-tutor5@example.com", "tutor")
    await client.put(
        "/api/v1/tutors/me/subjects",
        headers=hidden["headers"],
        json={"selections": [{"subject_id": ids["math_id"], "direction_ids": []}]},
    )
    hide_resp = await client.patch("/api/v1/tutors/me", headers=hidden["headers"], json={"is_hidden": True})
    assert hide_resp.status_code == 200, hide_resp.text

    body = (await client.get("/api/v1/subjects")).json()
    math = next(s for s in body if s["id"] == ids["math_id"])
    music = next(s for s in body if s["id"] == ids["music_id"])
    # Two directions of the same subject must not double-count the same tutor, and the
    # hidden profile is excluded exactly as it is from the catalog.
    assert math["tutors_count"] == 1
    assert music["tutors_count"] == 0
