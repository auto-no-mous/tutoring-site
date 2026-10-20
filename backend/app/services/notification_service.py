import datetime as dt
import logging
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking
from app.models.enums import (
    BookingStatus,
    EmailKind,
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
    SystemNotificationEvent,
)
from app.models.notification import BookingReminder, NotificationLog
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.user import MAX_REMINDER_LEAD_MINUTES, NotificationSettings
from app.services import system_notification_service
from app.services.email_service import send_email
from app.services.email_templates import render_email
from app.services.schedule_service import MSK
from app.services.telegram_service import send_telegram_message
from app.utils.time import ensure_aware, utcnow


logger = logging.getLogger("app.notifications")


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    event_type: NotificationEvent,
    title: str,
    body: str,
    *,
    email_html: str | None = None,
    email_text: str | None = None,
) -> None:
    """Dispatches a notification over the channels the user chose in Settings
    (User.notification_settings: per channel - on/off and which events, section 2.7).
    Best-effort: failures are logged to NotificationLog and swallowed so a
    misconfigured channel never breaks the calling business operation (booking,
    chat message, etc.).

    `email_html` даёт письму фирменное оформление вместо голого текста; в
    Telegram в любом случае уходит короткий текстовый вариант."""
    user = await db.get(User, user_id)
    if user is None:
        return

    prefs = notification_settings(user)
    for channel in NotificationChannel:
        if prefs.channel(channel).wants(event_type):
            await _deliver(db, user, channel, event_type, title, body, email_html=email_html, email_text=email_text)


def notification_settings(user: User) -> NotificationSettings:
    return NotificationSettings.model_validate(user.notification_settings or {})


def _destination(user: User, channel: NotificationChannel) -> str | None:
    return user.telegram_chat_id if channel == NotificationChannel.TELEGRAM else user.email


async def _deliver(
    db: AsyncSession,
    user: User,
    channel: NotificationChannel,
    event_type: NotificationEvent,
    title: str,
    body: str,
    *,
    email_html: str | None = None,
    email_text: str | None = None,
) -> bool:
    """Отправляет в один канал, если туда есть куда слать (Telegram привязан, почта
    указана). False - адреса нет, ничего не ушло."""
    destination = _destination(user, channel)
    if not destination:
        return False
    if channel == NotificationChannel.EMAIL:
        await _dispatch(db, user.id, channel, event_type, title, email_text or body, destination, email_html=email_html)
    else:
        await _dispatch(db, user.id, channel, event_type, title, body, destination)
    return True


async def notify_tutor(
    db: AsyncSession, tutor_id: uuid.UUID, event_type: NotificationEvent, title: str, body: str
) -> None:
    profile = await db.get(TutorProfile, tutor_id)
    if profile is None:
        return
    await notify(db, profile.user_id, event_type, title, body)


async def notify_first_booking(
    db: AsyncSession,
    *,
    student: User,
    tutor_user: User,
    start_at: dt.datetime,
    lesson_name: str | None = None,
) -> None:
    """Письмо о ПЕРВОМ занятии этой пары - обоим участникам.

    Именно первом: для репетитора это "пришёл новый ученик", для ученика -
    "занятия с этим репетитором начались". На повторные записи уходит обычное
    короткое уведомление NEW_BOOKING (см. booking_service.create_student_booking),
    иначе на каждую запись в серии сыпалось бы по два письма.

    Ходит через notify(), поэтому уважает выбранные пользователем каналы и
    попадает и в NotificationLog, и в журнал почты админки.
    """
    start_msk = ensure_aware(start_at).astimezone(MSK)
    when = f"{start_msk:%d.%m.%Y} в {start_msk:%H:%M} (МСК)"
    lesson_suffix = f" ({lesson_name})" if lesson_name else ""
    cabinet_url = f"{settings.frontend_base_url.rstrip('/')}/cabinet?tab=bookings"

    student_title = "Вы записались на занятие"
    student_body = (
        f"Занятие с {tutor_user.display_name}{lesson_suffix} — {when}"
        f"{local_time_hint(student, start_at)}."
    )
    student_text, student_html = render_email(
        heading=student_title,
        intro=f"{student_body} Это ваше первое занятие с этим репетитором — детали и ссылка на встречу будут в личном кабинете.",
        button_label="Мои занятия",
        button_url=cabinet_url,
        note="Отменить или перенести занятие можно там же, в карточке занятия.",
    )
    await notify(
        db,
        student.id,
        NotificationEvent.NEW_BOOKING,
        student_title,
        student_body,
        email_html=student_html,
        email_text=student_text,
    )

    tutor_title = "К вам записался новый ученик"
    tutor_body = f"{student.display_name} записался(-ась) на {when}{lesson_suffix}."
    tutor_text, tutor_html = render_email(
        heading=tutor_title,
        intro=f"{tutor_body} Раньше занятий с этим учеником не было.",
        button_label="Открыть расписание",
        button_url=cabinet_url,
        note="Ссылку на занятие можно добавить в карточке занятия в личном кабинете.",
    )
    await notify(
        db,
        tutor_user.id,
        NotificationEvent.NEW_BOOKING,
        tutor_title,
        tutor_body,
        email_html=tutor_html,
        email_text=tutor_text,
    )


def local_time_hint(user: User, moment: dt.datetime) -> str:
    """" - у вас это 16:00" для того, кто живёт не по Москве, иначе пустая строка.

    Время на сайте и в письмах всегда московское (раздел 6 project_description.md):
    один и тот же час у репетитора и у ученика - единственный способ не путаться при
    переносах. Но ученику из другого пояса одного московского числа мало, а баннер в
    письмо не вставишь - поэтому здесь короткая подсказка.
    """
    zone = (user.timezone or "").strip()
    if not zone or zone == "Europe/Moscow":
        return ""
    try:
        local = ensure_aware(moment).astimezone(ZoneInfo(zone))
    except (ZoneInfoNotFoundError, ValueError):
        # Пояс мог остаться мусорным (поле годами было свободным текстом) - тогда
        # просто молчим, вместо того чтобы ронять уведомление.
        return ""
    return f" — у вас это {local:%H:%M}"


def _reminder_email(
    other_name: str, start_msk: dt.datetime, for_tutor: bool, local_hint: str = ""
) -> tuple[str, str]:
    """Фирменное письмо-напоминание. Текст в мессенджер остаётся коротким."""
    when = f"{start_msk:%d.%m.%Y} в {start_msk:%H:%M} (МСК){local_hint}"
    return render_email(
        heading="Скоро занятие",
        intro=(
            f"Занятие с {other_name} начнётся {when}."
            if for_tutor
            else f"Ваше занятие с {other_name} начнётся {when}."
        ),
        button_label="Открыть занятие",
        button_url=f"{settings.frontend_base_url.rstrip('/')}/cabinet?tab=bookings",
        note="Ссылка на встречу — в карточке занятия. Отключить напоминания или сменить канал можно в Настройках.",
    )


async def _dispatch(
    db: AsyncSession,
    user_id: uuid.UUID,
    channel: NotificationChannel,
    event_type: NotificationEvent,
    title: str,
    body: str,
    destination: str,
    email_html: str | None = None,
) -> None:
    log = NotificationLog(
        user_id=user_id,
        channel=channel.value,
        event_type=event_type.value,
        payload=body,
        status=NotificationStatus.PENDING.value,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    try:
        if channel == NotificationChannel.TELEGRAM:
            await send_telegram_message(destination, f"{title}\n\n{body}")
        else:
            # kind/user_id - чтобы письмо было видно в журнале почты админки с
            # привязкой к пользователю (см. app.services.email_log_service).
            await send_email(
                destination, title, body, email_html, kind=EmailKind.NOTIFICATION.value, user_id=user_id
            )
        log.status = NotificationStatus.SENT.value
        log.sent_at = utcnow()
    except Exception as exc:  # noqa: BLE001 - notifications must never break the caller
        logger.warning("Notification dispatch failed (channel=%s, event=%s): %s", channel, event_type, exc)
        log.status = NotificationStatus.FAILED.value
        log.error = str(exc)

    await db.commit()


def _is_due(start_at: dt.datetime, now: dt.datetime, lead_minutes: int, tolerance_minutes: float) -> bool:
    target = start_at - dt.timedelta(minutes=lead_minutes)
    return abs((now - target).total_seconds()) <= tolerance_minutes * 60


async def send_upcoming_reminders(db: AsyncSession, tolerance_minutes: float = 10.0) -> int:
    """Напоминает участникам индивидуального занятия, что оно скоро. У каждого канала
    своё «за сколько минут» (User.notification_settings, Настройки -> «Уведомления»),
    так что в Telegram напоминание может прийти за 15 минут, а на почту за час -
    отправка отмечается по каждому каналу отдельно (BookingReminder). Репетитор и
    ученик настраивают это каждый для себя и напоминаются независимо.

    Плюс запись в «Системные уведомления» на сайте: она приходит вместе с самым ранним
    из включённых напоминаний, а если в каналах они выключены - за
    DEFAULT_SITE_REMINDER_MINUTES (отмечается в Booking.reminder_sent_at /
    student_reminder_sent_at).

    The default tolerance is sized against the scheduler cadence documented in
    ops/README.md (systemd timer, every 10 minutes) - a ±10 min window comfortably
    covers a 10-minute gap between runs with margin for scheduler jitter. If you run
    the external scheduler less often than that, widen this value accordingly or a
    reminder can be missed entirely (the window closes before the next run ever
    checks it). Each (booking, recipient, channel) is only ever reminded once.

    Возвращает, сколько напоминаний ушло в каналы (Telegram/почта)."""
    now = utcnow()
    window_end = now + dt.timedelta(minutes=MAX_REMINDER_LEAD_MINUTES + tolerance_minutes)

    result = await db.execute(
        select(Booking).where(
            Booking.status == BookingStatus.SCHEDULED.value,
            Booking.start_at > now,
            Booking.start_at <= window_end,
        )
    )
    bookings = list(result.scalars().all())

    sent = 0
    for booking in bookings:
        tutor_profile = await db.get(TutorProfile, booking.tutor_id)
        tutor_user = await db.get(User, tutor_profile.user_id) if tutor_profile else None
        student_user = await db.get(User, booking.student_id) if booking.student_id else None

        if tutor_user is not None:
            sent += await _remind(
                db, booking, tutor_user, now, tolerance_minutes,
                other_name=student_user.display_name if student_user else "учеником",
                for_tutor=True,
            )
        if student_user is not None:
            sent += await _remind(
                db, booking, student_user, now, tolerance_minutes,
                other_name=tutor_user.display_name if tutor_user else "репетитором",
                for_tutor=False,
            )

    await db.commit()
    return sent


# «Системные уведомления» на сайте приходят и тем, кто выключил напоминания в
# Telegram и на почту, - так было и при прежнем переключателе «Не присылать».
DEFAULT_SITE_REMINDER_MINUTES = 60


async def _remind(
    db: AsyncSession,
    booking: Booking,
    user: User,
    now: dt.datetime,
    tolerance_minutes: float,
    *,
    other_name: str,
    for_tutor: bool,
) -> int:
    start_at = ensure_aware(booking.start_at)
    start_msk = start_at.astimezone(MSK)
    hint = "" if for_tutor else local_time_hint(user, start_at)
    prefs = notification_settings(user)

    already = set(
        (
            await db.scalars(
                select(BookingReminder.channel).where(
                    BookingReminder.booking_id == booking.id, BookingReminder.user_id == user.id
                )
            )
        ).all()
    )

    sent = 0
    leads: list[int] = []
    for channel in NotificationChannel:
        channel_prefs = prefs.channel(channel)
        if not channel_prefs.wants(NotificationEvent.UPCOMING_REMINDER) or not _destination(user, channel):
            continue
        leads.append(channel_prefs.reminder_lead_minutes)
        if channel.value in already or not _is_due(start_at, now, channel_prefs.reminder_lead_minutes, tolerance_minutes):
            continue
        reminder_text, reminder_html = _reminder_email(other_name, start_msk, for_tutor=for_tutor, local_hint=hint)
        await _deliver(
            db, user, channel, NotificationEvent.UPCOMING_REMINDER,
            "Скоро занятие",
            f"Занятие с {other_name} начнётся {start_msk:%d.%m.%Y %H:%M} (МСК){hint}.",
            email_html=reminder_html, email_text=reminder_text,
        )
        db.add(BookingReminder(booking_id=booking.id, user_id=user.id, channel=channel.value, sent_at=now))
        sent += 1

    site_lead = max(leads, default=DEFAULT_SITE_REMINDER_MINUTES)
    site_sent_attr = "reminder_sent_at" if for_tutor else "student_reminder_sent_at"
    if getattr(booking, site_sent_attr) is None and _is_due(start_at, now, site_lead, tolerance_minutes):
        name_param = {"student_name": other_name} if for_tutor else {"tutor_name": other_name}
        await system_notification_service.notify(
            db, user.id, SystemNotificationEvent.UPCOMING_LESSON_REMINDER,
            **name_param, time=f"{start_msk:%H:%M}", lead_minutes=str(site_lead),
        )
        setattr(booking, site_sent_attr, now)

    return sent
