"""Каналы уведомлений и письмо о первом занятии пары."""

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationChannelPref, NotificationEvent
from app.models.user import User
from app.services import notification_service

MSK = ZoneInfo("Europe/Moscow")


@pytest.fixture
def channels(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Перехватывает оба канала доставки, чтобы тесты не ходили наружу."""
    calls: dict[str, list[Any]] = {"email": [], "telegram": []}

    async def fake_email(to: str, subject: str, body: str, html_body: str | None = None, **kwargs: Any) -> bool:
        calls["email"].append({"to": to, "subject": subject, "body": body, "html": html_body})
        return True

    async def fake_telegram(chat_id: str, text: str) -> None:
        calls["telegram"].append({"chat_id": chat_id, "text": text})

    monkeypatch.setattr(notification_service, "send_email", fake_email)
    monkeypatch.setattr(notification_service, "send_telegram_message", fake_telegram)
    return calls


async def _make_user(db_session: AsyncSession, channel: str, *, with_telegram: bool = True) -> User:
    user = User(
        role="student",
        email="channel-test@example.com",
        display_name="Тест Тестов",
        first_name="Тест",
        last_name="Тестов",
        telegram_chat_id="12345" if with_telegram else None,
        notification_channel=channel,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.parametrize(
    ("channel", "expect_email", "expect_telegram"),
    [
        (NotificationChannelPref.BOTH.value, 1, 1),
        (NotificationChannelPref.EMAIL.value, 1, 0),
        (NotificationChannelPref.TELEGRAM.value, 0, 1),
        (NotificationChannelPref.OFF.value, 0, 0),
    ],
)
async def test_notify_respects_channel_preference(
    db_session: AsyncSession,
    channels: dict[str, list[Any]],
    channel: str,
    expect_email: int,
    expect_telegram: int,
) -> None:
    user = await _make_user(db_session, channel)

    await notification_service.notify(
        db_session, user.id, NotificationEvent.UPCOMING_REMINDER, "Скоро занятие", "Через час."
    )

    assert len(channels["email"]) == expect_email
    assert len(channels["telegram"]) == expect_telegram


async def test_notify_sends_branded_html_when_given(
    db_session: AsyncSession, channels: dict[str, list[Any]]
) -> None:
    user = await _make_user(db_session, NotificationChannelPref.EMAIL.value, with_telegram=False)

    await notification_service.notify(
        db_session,
        user.id,
        NotificationEvent.NEW_BOOKING,
        "Тема",
        "короткий текст",
        email_html="<p>оформленное письмо</p>",
        email_text="длинный текст письма",
    )

    sent = channels["email"][0]
    assert sent["html"] == "<p>оформленное письмо</p>"
    # В письмо идёт развёрнутый текст, короткий остаётся для мессенджера.
    assert sent["body"] == "длинный текст письма"


async def test_first_booking_notifies_both_sides(
    db_session: AsyncSession, channels: dict[str, list[Any]]
) -> None:
    student = await _make_user(db_session, NotificationChannelPref.EMAIL.value, with_telegram=False)
    tutor_user = User(
        role="tutor",
        email="tutor-first@example.com",
        display_name="Анна Сергеевна",
        first_name="Анна",
        last_name="Смирнова",
        notification_channel=NotificationChannelPref.EMAIL.value,
        is_active=True,
    )
    db_session.add(tutor_user)
    await db_session.commit()
    await db_session.refresh(tutor_user)

    await notification_service.notify_first_booking(
        db_session,
        student=student,
        tutor_user=tutor_user,
        start_at=dt.datetime(2026, 9, 1, 12, 0, tzinfo=MSK),
        lesson_name="Занятие",
    )

    assert len(channels["email"]) == 2
    to_student, to_tutor = channels["email"]
    assert to_student["to"] == student.email
    assert to_student["subject"] == "Вы записались на занятие"
    assert "Анна Сергеевна" in to_student["body"]
    assert to_tutor["to"] == tutor_user.email
    assert to_tutor["subject"] == "К вам записался новый ученик"
    assert "Тест Тестов" in to_tutor["body"]
    # Оба письма - в фирменном оформлении, а не голым текстом.
    assert to_student["html"] and to_tutor["html"]


async def test_first_booking_email_only_once_per_pair(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Второе занятие с тем же репетитором - обычное короткое уведомление."""
    first_booking_calls: list[Any] = []

    async def fake_first(db: Any, **kwargs: Any) -> None:
        first_booking_calls.append(kwargs)

    from app.services import booking_service

    monkeypatch.setattr(booking_service.notification_service, "notify_first_booking", fake_first)

    from tests.test_bookings import _next_weekday_datetime, _register, _setup_tutor

    tutor = await _setup_tutor(client, "first-booking-tutor@example.com")
    student = await _register(client, "first-booking-student@example.com", "student")
    slot = _next_weekday_datetime(0, 10)

    for offset_hours in (0, 2):
        resp = await client.post(
            "/api/v1/bookings",
            headers=student["headers"],
            json={
                "tutor_id": tutor["id"],
                "lesson_type_id": tutor["lesson_type_id"],
                "start_at": (slot + dt.timedelta(hours=offset_hours)).isoformat(),
                "repeat_weekly": False,
            },
        )
        assert resp.status_code == 201, resp.text

    assert len(first_booking_calls) == 1


async def test_linking_telegram_switches_the_channel_on_once(db_session: AsyncSession) -> None:
    """Привязали мессенджер - значит хотят получать в него уведомления. Иначе выходило
    странно: человек подключил Telegram, а сообщения туда не идут, потому что в
    настройках осталось «только почта»."""
    from app.services import telegram_service

    user = await _make_user(db_session, NotificationChannelPref.EMAIL.value, with_telegram=False)
    user.telegram_link_token = "link-token"
    user.telegram_link_token_expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)
    await db_session.commit()

    linked = await telegram_service.link_chat_by_token(db_session, "link-token", "99887")
    assert linked is not None
    assert linked.telegram_chat_id == "99887"
    assert linked.notification_channel == NotificationChannelPref.BOTH.value

    # Дальше выбор снова за пользователем: переключение происходит в момент привязки,
    # а не навязывается постоянно.
    linked.notification_channel = NotificationChannelPref.EMAIL.value
    await db_session.commit()
    await db_session.refresh(linked)
    assert linked.notification_channel == NotificationChannelPref.EMAIL.value


async def test_expired_link_token_changes_nothing(db_session: AsyncSession) -> None:
    from app.services import telegram_service

    user = await _make_user(db_session, NotificationChannelPref.EMAIL.value, with_telegram=False)
    user.telegram_link_token = "stale-token"
    user.telegram_link_token_expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    assert await telegram_service.link_chat_by_token(db_session, "stale-token", "99887") is None
    await db_session.refresh(user)
    assert user.telegram_chat_id is None
    assert user.notification_channel == NotificationChannelPref.EMAIL.value
