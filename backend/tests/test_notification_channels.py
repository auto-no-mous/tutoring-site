"""Каналы уведомлений и письмо о первом занятии пары."""

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationEvent
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


def _prefs(*, telegram: bool = True, email: bool = True, **events: bool) -> dict[str, Any]:
    """Настройки уведомлений: какие каналы включены и, при необходимости, отдельные
    события в обоих (new_booking=False и т.п.)."""
    return {
        "telegram": {"enabled": telegram, **events},
        "email": {"enabled": email, **events},
    }


EMAIL_ONLY = _prefs(telegram=False)


async def _make_user(db_session: AsyncSession, prefs: dict[str, Any], *, with_telegram: bool = True) -> User:
    user = User(
        role="student",
        email="channel-test@example.com",
        display_name="Тест Тестов",
        first_name="Тест",
        last_name="Тестов",
        telegram_chat_id="12345" if with_telegram else None,
        notification_settings=prefs,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.parametrize(
    ("telegram", "email", "expect_telegram", "expect_email"),
    [(True, True, 1, 1), (False, True, 0, 1), (True, False, 1, 0), (False, False, 0, 0)],
)
async def test_notify_respects_enabled_channels(
    db_session: AsyncSession,
    channels: dict[str, list[Any]],
    telegram: bool,
    email: bool,
    expect_telegram: int,
    expect_email: int,
) -> None:
    user = await _make_user(db_session, _prefs(telegram=telegram, email=email))

    await notification_service.notify(db_session, user.id, NotificationEvent.NEW_BOOKING, "Новая запись", "Завтра.")

    assert len(channels["email"]) == expect_email
    assert len(channels["telegram"]) == expect_telegram


async def test_notify_respects_per_event_switches_in_each_channel(
    db_session: AsyncSession, channels: dict[str, list[Any]]
) -> None:
    """Переносы - только в Telegram, новые записи - только на почту."""
    user = await _make_user(
        db_session,
        {"telegram": {"new_booking": False}, "email": {"schedule_change": False}},
    )

    await notification_service.notify(db_session, user.id, NotificationEvent.SCHEDULE_CHANGE, "Перенос", "...")
    await notification_service.notify(db_session, user.id, NotificationEvent.NEW_BOOKING, "Запись", "...")

    assert [c["text"].startswith("Перенос") for c in channels["telegram"]] == [True]
    assert [c["subject"] for c in channels["email"]] == ["Запись"]


async def test_events_without_own_switch_follow_the_channel(
    db_session: AsyncSession, channels: dict[str, list[Any]]
) -> None:
    """Сообщения в чате и т.п. отдельного пункта не имеют - идут, пока канал включён."""
    user = await _make_user(
        db_session, _prefs(telegram=False, new_booking=False, schedule_change=False, reminder=False)
    )

    await notification_service.notify(db_session, user.id, NotificationEvent.NEW_MESSAGE, "Сообщение", "...")

    assert len(channels["email"]) == 1
    assert len(channels["telegram"]) == 0


async def test_missing_settings_mean_defaults(db_session: AsyncSession, channels: dict[str, list[Any]]) -> None:
    """Старые записи и новые каналы без сохранённых настроек - всё включено."""
    user = await _make_user(db_session, {})

    await notification_service.notify(db_session, user.id, NotificationEvent.SCHEDULE_CHANGE, "Перенос", "...")

    assert len(channels["email"]) == 1
    assert len(channels["telegram"]) == 1


async def test_notify_sends_branded_html_when_given(
    db_session: AsyncSession, channels: dict[str, list[Any]]
) -> None:
    user = await _make_user(db_session, EMAIL_ONLY, with_telegram=False)

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
    student = await _make_user(db_session, EMAIL_ONLY, with_telegram=False)
    tutor_user = User(
        role="tutor",
        email="tutor-first@example.com",
        display_name="Анна Сергеевна",
        first_name="Анна",
        last_name="Смирнова",
        notification_settings=EMAIL_ONLY,
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
    странно: человек подключил Telegram, а сообщения туда не идут, потому что канал
    в настройках выключен."""
    from app.services import telegram_service

    user = await _make_user(db_session, EMAIL_ONLY, with_telegram=False)
    user.telegram_link_token = "link-token"
    user.telegram_link_token_expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)
    await db_session.commit()

    linked = await telegram_service.link_chat_by_token(db_session, "link-token", "99887")
    assert linked is not None
    assert linked.telegram_chat_id == "99887"
    assert linked.notification_settings["telegram"]["enabled"] is True
    # Почта как была включена, так и осталась.
    assert linked.notification_settings["email"]["enabled"] is True

    # Дальше выбор снова за пользователем: переключение происходит в момент привязки,
    # а не навязывается постоянно.
    linked.notification_settings = EMAIL_ONLY
    await db_session.commit()
    await db_session.refresh(linked)
    assert linked.notification_settings["telegram"]["enabled"] is False


async def test_expired_link_token_changes_nothing(db_session: AsyncSession) -> None:
    from app.services import telegram_service

    user = await _make_user(db_session, EMAIL_ONLY, with_telegram=False)
    user.telegram_link_token = "stale-token"
    user.telegram_link_token_expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    assert await telegram_service.link_chat_by_token(db_session, "stale-token", "99887") is None
    await db_session.refresh(user)
    assert user.telegram_chat_id is None
    assert user.notification_settings == EMAIL_ONLY


async def _booking_in(db_session: AsyncSession, student: User, minutes: int) -> Any:
    """Занятие через `minutes` минут у ученика student с отдельным репетитором."""
    from app.models.booking import Booking
    from app.models.enums import BookingStatus
    from app.models.tutor import TutorProfile

    tutor_user = User(
        role="tutor", email="lead-tutor@example.com", display_name="Анна Сергеевна",
        first_name="Анна", last_name="Смирнова", notification_settings=_prefs(telegram=False, reminder=False),
        is_active=True,
    )
    db_session.add(tutor_user)
    await db_session.flush()
    profile = TutorProfile(user_id=tutor_user.id, slug="lead-tutor")
    db_session.add(profile)
    await db_session.flush()
    start_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    booking = Booking(
        tutor_id=profile.id, student_id=student.id, start_at=start_at,
        end_at=start_at + dt.timedelta(hours=1), status=BookingStatus.SCHEDULED.value,
    )
    db_session.add(booking)
    await db_session.commit()
    return booking


async def _site_reminders(db_session: AsyncSession, user: User) -> list[str]:
    from sqlalchemy import select

    from app.models.system_notification import SystemNotification

    rows = await db_session.scalars(
        select(SystemNotification).where(
            SystemNotification.user_id == user.id, SystemNotification.event_type == "upcoming_lesson_reminder"
        )
    )
    return [r.body for r in rows.all()]


async def test_reminder_lead_time_is_per_channel(db_session: AsyncSession, channels: dict[str, list[Any]]) -> None:
    """Telegram - за 15 минут, почта - за 60: каждое приходит в своё время и один раз."""
    student = await _make_user(
        db_session,
        {"telegram": {"reminder_lead_minutes": 15}, "email": {"reminder_lead_minutes": 60}},
    )
    booking = await _booking_in(db_session, student, 60)

    assert await notification_service.send_upcoming_reminders(db_session) == 1
    assert len(channels["email"]) == 1 and len(channels["telegram"]) == 0
    # На сайте - вместе с самым ранним напоминанием и с его временем.
    assert len(site := await _site_reminders(db_session, student)) == 1
    assert "60" in site[0]

    # Через 45 минут подходит очередь Telegram; почта второй раз не уходит.
    booking.start_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)
    await db_session.commit()
    assert await notification_service.send_upcoming_reminders(db_session) == 1
    assert len(channels["email"]) == 1 and len(channels["telegram"]) == 1
    assert len(await _site_reminders(db_session, student)) == 1

    assert await notification_service.send_upcoming_reminders(db_session) == 0


async def test_reminder_switched_off_in_a_channel(db_session: AsyncSession, channels: dict[str, list[Any]]) -> None:
    student = await _make_user(db_session, {"telegram": {"reminder": False}})
    await _booking_in(db_session, student, 60)

    assert await notification_service.send_upcoming_reminders(db_session) == 1
    assert len(channels["email"]) == 1 and len(channels["telegram"]) == 0


async def test_site_reminder_stays_when_channel_reminders_are_off(
    db_session: AsyncSession, channels: dict[str, list[Any]]
) -> None:
    """Как и при прежнем «Не присылать»: в Telegram и на почту ничего, а на сайте
    напоминание за час всё равно появляется."""
    student = await _make_user(db_session, _prefs(telegram=False, email=False))
    await _booking_in(db_session, student, 60)

    assert await notification_service.send_upcoming_reminders(db_session) == 0
    assert channels == {"email": [], "telegram": []}
    assert len(await _site_reminders(db_session, student)) == 1


async def test_reminder_not_marked_sent_without_an_address(
    db_session: AsyncSession, channels: dict[str, list[Any]]
) -> None:
    """Telegram включён, но не привязан: отправлять некуда - и после привязки
    напоминание всё ещё должно прийти."""
    student = await _make_user(db_session, _prefs(email=False), with_telegram=False)
    await _booking_in(db_session, student, 60)

    assert await notification_service.send_upcoming_reminders(db_session) == 0

    student.telegram_chat_id = "555"
    await db_session.commit()
    assert await notification_service.send_upcoming_reminders(db_session) == 1
    assert len(channels["telegram"]) == 1
