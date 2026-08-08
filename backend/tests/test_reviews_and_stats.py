import datetime as dt
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus


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


async def _insert_past_booking(
    db_session: AsyncSession, tutor_id: str, student_id: str, lesson_type_id: str, hours_ago: int, status: str = BookingStatus.SCHEDULED.value
) -> None:
    end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_ago)
    start = end - dt.timedelta(hours=1)
    db_session.add(
        Booking(
            tutor_id=uuid.UUID(tutor_id),
            student_id=uuid.UUID(student_id),
            lesson_type_id=uuid.UUID(lesson_type_id),
            start_at=start,
            end_at=end,
            status=status,
        )
    )
    await db_session.commit()


async def test_review_requires_past_lesson_and_upserts(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "rev-tutor1@example.com", "tutor")
    student = await _register(client, "rev-student1@example.com", "student")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]

    denied = await client.post(
        f"/api/v1/tutors/{tutor_id}/reviews", headers=student["headers"], json={"rating": 5, "text": "Отлично"}
    )
    assert denied.status_code == 403

    await _insert_past_booking(db_session, tutor_id, student["user"]["id"], lesson_type_id, hours_ago=5)

    create_resp = await client.post(
        f"/api/v1/tutors/{tutor_id}/reviews", headers=student["headers"], json={"rating": 4, "text": "Хорошо"}
    )
    assert create_resp.status_code == 200, create_resp.text
    assert create_resp.json()["rating"] == 4

    update_resp = await client.post(
        f"/api/v1/tutors/{tutor_id}/reviews", headers=student["headers"], json={"rating": 5, "text": "Отлично!"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["rating"] == 5

    reviews = (await client.get(f"/api/v1/tutors/{tutor_id}/reviews")).json()
    assert len(reviews) == 1
    assert reviews[0]["rating"] == 5
    assert reviews[0]["student_display_name"] == "student Test"

    rating = (await client.get(f"/api/v1/tutors/{tutor_id}/rating")).json()
    assert rating["average"] == 5.0
    assert rating["count"] == 1


async def test_rating_average_across_students(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "rev-tutor2@example.com", "tutor")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]

    ratings = [2, 4]
    for i, rating in enumerate(ratings):
        student = await _register(client, f"rev-student2-{i}@example.com", "student")
        await _insert_past_booking(db_session, tutor_id, student["user"]["id"], lesson_type_id, hours_ago=5)
        resp = await client.post(
            f"/api/v1/tutors/{tutor_id}/reviews", headers=student["headers"], json={"rating": rating}
        )
        assert resp.status_code == 200

    summary = (await client.get(f"/api/v1/tutors/{tutor_id}/rating")).json()
    assert summary["count"] == 2
    assert summary["average"] == 3.0


async def test_tutor_and_student_stats(client: AsyncClient, db_session: AsyncSession) -> None:
    tutor = await _register(client, "stats-tutor1@example.com", "tutor")
    tutor_id = (await client.get("/api/v1/tutors/me", headers=tutor["headers"])).json()["id"]
    lesson_type_id = (
        await client.post(
            "/api/v1/tutors/me/lesson-types",
            headers=tutor["headers"],
            json={"name": "Занятие", "format": "individual", "duration_minutes": 60, "price": 1000},
        )
    ).json()["id"]

    student1 = await _register(client, "stats-student1@example.com", "student")
    student2 = await _register(client, "stats-student2@example.com", "student")

    # Two held lessons with student1, one held with student2, one cancelled (excluded).
    await _insert_past_booking(db_session, tutor_id, student1["user"]["id"], lesson_type_id, hours_ago=5)
    await _insert_past_booking(db_session, tutor_id, student1["user"]["id"], lesson_type_id, hours_ago=10)
    await _insert_past_booking(db_session, tutor_id, student2["user"]["id"], lesson_type_id, hours_ago=15)
    await _insert_past_booking(
        db_session, tutor_id, student2["user"]["id"], lesson_type_id, hours_ago=20,
        status=BookingStatus.CANCELLED_BY_STUDENT.value,
    )

    # Homework: one done, one pending, for student1.
    await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "ДЗ 1", "submission_mode": "mark_done", "student_ids": [student1["user"]["id"]],
            "content_url": "https://example.com/1",
        },
    )
    submission1 = (await client.get("/api/v1/homework/me", headers=student1["headers"])).json()[0]
    await client.post(f"/api/v1/homework/submissions/{submission1['submission_id']}/done", headers=student1["headers"])

    await client.post(
        "/api/v1/homework",
        headers=tutor["headers"],
        data={
            "title": "ДЗ 2", "submission_mode": "mark_done", "student_ids": [student1["user"]["id"]],
            "content_url": "https://example.com/2",
        },
    )

    tutor_stats = (await client.get("/api/v1/stats/tutor/me", headers=tutor["headers"])).json()
    assert tutor_stats["total_lessons_held"] == 3  # cancelled one excluded
    assert tutor_stats["homeworks_done"] == 1
    assert tutor_stats["unique_students_this_month"] == 2

    student1_stats = (await client.get("/api/v1/stats/student/me", headers=student1["headers"])).json()
    assert student1_stats["lessons_completed"] == 2
    assert student1_stats["homework_total"] == 2
    assert student1_stats["homework_done"] == 1
    assert student1_stats["homework_completion_rate"] == 0.5

    student2_stats = (await client.get("/api/v1/stats/student/me", headers=student2["headers"])).json()
    assert student2_stats["lessons_completed"] == 1  # the cancelled one doesn't count
