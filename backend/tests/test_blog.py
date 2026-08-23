from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.utils.time import utcnow


async def _admin_headers(client: AsyncClient, db_session: AsyncSession, email: str = "blog-admin@example.com") -> dict:
    admin = User(
        role="admin",
        email=email,
        password_hash=hash_password("adminpass1"),
        first_name="Админ",
        last_name="Блогов",
        display_name="Блогов Админ",
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


async def _register_student(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret1",
            "first_name": "Тест",
            "last_name": "Ученик",
            "role": "student",
            "pd_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def test_draft_is_invisible_publicly_until_published(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session)

    created = await client.post(
        "/api/v1/admin/blog",
        headers=headers,
        json={"title": "Как готовиться к ЕГЭ", "body": "<p>Текст статьи</p>"},
    )
    assert created.status_code == 201, created.text
    post = created.json()
    assert post["is_published"] is False
    assert post["published_at"] is None

    assert (await client.get("/api/v1/blog")).json()["total"] == 0
    assert (await client.get(f"/api/v1/blog/{post['slug']}")).status_code == 404

    published = await client.patch(
        f"/api/v1/admin/blog/{post['id']}", headers=headers, json={"is_published": True}
    )
    assert published.status_code == 200, published.text
    assert published.json()["published_at"] is not None

    listing = await client.get("/api/v1/blog")
    assert listing.json()["total"] == 1
    # Карточка не тащит тело статьи.
    assert "body" not in listing.json()["items"][0]

    detail = await client.get(f"/api/v1/blog/{post['slug']}")
    assert detail.status_code == 200
    assert detail.json()["body"] == "<p>Текст статьи</p>"
    assert detail.json()["author_name"] == "Блогов Админ"


async def test_slug_is_transliterated_and_deduplicated(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session, "blog-admin2@example.com")

    first = await client.post("/api/v1/admin/blog", headers=headers, json={"title": "Итоги года"})
    second = await client.post("/api/v1/admin/blog", headers=headers, json={"title": "Итоги года"})

    assert first.json()["slug"] == "itogi-goda"
    assert second.json()["slug"] == "itogi-goda-2"

    # Явно заданный slug побеждает заголовок.
    explicit = await client.post(
        "/api/v1/admin/blog", headers=headers, json={"title": "Что-то", "slug": "my-custom-url"}
    )
    assert explicit.json()["slug"] == "my-custom-url"


async def test_summary_falls_back_to_the_start_of_the_body(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session, "blog-admin3@example.com")

    auto = await client.post(
        "/api/v1/admin/blog",
        headers=headers,
        json={"title": "Без описания", "body": "<p>Первый абзац.</p><p>Второй абзац.</p>"},
    )
    assert auto.json()["summary"] == "Первый абзац. Второй абзац."

    explicit = await client.post(
        "/api/v1/admin/blog",
        headers=headers,
        json={"title": "С описанием", "body": "<p>Текст</p>", "summary": "Своё описание"},
    )
    assert explicit.json()["summary"] == "Своё описание"


async def test_body_is_sanitized_on_the_way_in(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session, "blog-admin4@example.com")

    created = await client.post(
        "/api/v1/admin/blog",
        headers=headers,
        json={
            "title": "Опасная статья",
            "body": (
                '<p>Текст</p><script>alert(1)</script>'
                '<img src="https://evil.example/track.gif">'
                '<img src="/files/blog-images/ok.png" class="rt-img-left">'
                '<a href="javascript:alert(1)">клик</a>'
            ),
        },
    )
    body = created.json()["body"]
    assert "<script>" not in body
    assert "evil.example" not in body
    assert 'src="/files/blog-images/ok.png"' in body
    assert 'class="rt-img-left"' in body
    assert "javascript:" not in body


async def test_republishing_keeps_the_original_publication_date(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _admin_headers(client, db_session, "blog-admin5@example.com")
    post = (
        await client.post(
            "/api/v1/admin/blog", headers=headers, json={"title": "Статья", "is_published": True}
        )
    ).json()
    first_published_at = post["published_at"]
    assert first_published_at is not None

    await client.patch(f"/api/v1/admin/blog/{post['id']}", headers=headers, json={"is_published": False})
    again = await client.patch(
        f"/api/v1/admin/blog/{post['id']}", headers=headers, json={"is_published": True}
    )
    assert again.json()["published_at"] == first_published_at


async def test_blog_administration_is_admin_only(client: AsyncClient, db_session: AsyncSession) -> None:
    admin_headers = await _admin_headers(client, db_session, "blog-admin6@example.com")
    post = (await client.post("/api/v1/admin/blog", headers=admin_headers, json={"title": "Статья"})).json()

    student_headers = await _register_student(client, "blog-student@example.com")

    assert (await client.get("/api/v1/admin/blog", headers=student_headers)).status_code == 403
    assert (
        await client.post("/api/v1/admin/blog", headers=student_headers, json={"title": "Моя статья"})
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/admin/blog/{post['id']}", headers=student_headers, json={"title": "Взлом"}
        )
    ).status_code == 403
    assert (await client.delete(f"/api/v1/admin/blog/{post['id']}", headers=student_headers)).status_code == 403
    # Анонимно тоже нельзя.
    assert (await client.get("/api/v1/admin/blog")).status_code == 401


async def test_admin_can_delete_a_post(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _admin_headers(client, db_session, "blog-admin7@example.com")
    post = (
        await client.post(
            "/api/v1/admin/blog", headers=headers, json={"title": "Черновик", "is_published": True}
        )
    ).json()

    assert (await client.delete(f"/api/v1/admin/blog/{post['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"/api/v1/blog/{post['slug']}")).status_code == 404
    assert (await client.get("/api/v1/admin/blog", headers=headers)).json() == []
