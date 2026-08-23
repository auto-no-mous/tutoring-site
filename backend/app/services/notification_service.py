import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking
from app.models.enums import (
    BookingStatus,
    EmailKind,
    NotificationChannel,
    NotificationChannelPref,
    NotificationEvent,
    NotificationStatus,
    SystemNotificationEvent,
)
from app.models.notification import NotificationLog
from app.models.tutor import TutorProfile
from app.models.user import User
from app.services import system_notification_service
from app.services.email_service import send_email
from app.services.email_templates import render_email
from app.services.schedule_service import MSK
from app.services.telegram_service import send_telegram_message
from app.utils.time import ensure_aware, utcnow

# Cap on Settings' "уведомлять за N минут" field (schemas/user.py) - a week is more
# than generous, and bounds how far ahead send_upcoming_reminders has to scan.
MAX_REMINDER_LEAD_MINUTES = 7 * 24 * 60

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
    (User.notification_channel: off / email / telegram / both, section 2.7).
    Best-effort: failures are logged to NotificationLog and swallowed so a
    misconfigured channel never breaks the calling business operation (booking,
    chat message, etc.).

    `email_html` даёт письму фирменное оформление вместо голого текста; в
    Telegram в любом случае уходит короткий текстовый вариант."""
    user = await db.get(User, user_id)
    if user is None:
        return

    channel_pref = user.notification_channel
    if channel_pref == NotificationChannelPref.OFF.value:
        return

    wants_telegram = channel_pref in (NotificationChannelPref.TELEGRAM.value, NotificationChannelPref.BOTH.value)
    wants_email = channel_pref in (NotificationChannelPref.EMAIL.value, NotificationChannelPref.BOTH.value)

    if user.telegram_chat_id and wants_telegram:
        await _dispatch(db, user.id, NotificationChannel.TELEGRAM, event_type, title, body, user.telegram_chat_id)

    if user.email and wants_email:
        await _dispatch(
            db,
            user.id,
            NotificationChannel.EMAIL,
            event_type,
            title,
            email_text or body,
            user.email,
            email_html=email_html,
        )


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
    student_body = f"Занятие с {tutor_user.display_name}{lesson_suffix} — {when}."
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


def _reminder_email(other_name: str, start_msk: dt.datetime, for_tutor: bool) -> tuple[str, str]:
    """Фирменное письмо-напоминание. Текст в мессенджер остаётся коротким."""
    when = f"{start_msk:%d.%m.%Y} в {start_msk:%H:%M} (МСК)"
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
    """Notifies each participant of an individual lesson starting soon, at THEIR OWN
    configured lead time (User.reminder_lead_minutes, editable in Settings next to
    the Telegram connect button - default 60 min). Tutor and student are reminded
    independently since they can each set a different lead time, so a booking's two
    reminders (reminder_sent_at / student_reminder_sent_at) are tracked separately.

    The default tolerance is sized against the scheduler cadence documented in
    README.md ("Telegram-бот" section, systemd timer example: every 10 minutes) - a
    ±10 min window comfortably covers a 10-minute gap between runs with margin for
    scheduler jitter. If you run the external scheduler less often than that, widen
    this value accordingly or a reminder can be missed entirely (the window closes
    before the next run ever checks it).

    Meant to be run frequently (e.g. every minute) by an external scheduler - this
    codebase doesn't wire one up itself (see app/scripts/send_reminders.py,
    cron-friendly one-shot design; run-local.ps1 loops it for local testing). The
    tolerance window is what makes an infrequent/imprecise scheduler still work: as
    long as it runs at least once within +/-tolerance_minutes of the due moment, the
    reminder fires; each (booking, recipient) pair is only ever reminded once."""
    now = utcnow()
    window_end = now + dt.timedelta(minutes=MAX_REMINDER_LEAD_MINUTES + tolerance_minutes)

    result = await db.execute(
        select(Booking).where(
            Booking.status == BookingStatus.SCHEDULED.value,
            Booking.start_at > now,
            Booking.start_at <= window_end,
            (Booking.reminder_sent_at.is_(None)) | (Booking.student_reminder_sent_at.is_(None)),
        )
    )
    bookings = list(result.scalars().all())

    sent = 0
    for booking in bookings:
        start_at = ensure_aware(booking.start_at)
        start_msk = start_at.astimezone(MSK)
        time_str = f"{start_msk:%H:%M}"

        if booking.reminder_sent_at is None:
            tutor_profile = await db.get(TutorProfile, booking.tutor_id)
            tutor_user = await db.get(User, tutor_profile.user_id) if tutor_profile else None
            if tutor_user is not None and _is_due(start_at, now, tutor_user.reminder_lead_minutes, tolerance_minutes):
                student = await db.get(User, booking.student_id) if booking.student_id else None
                student_name = student.display_name if student else "учеником"
                reminder_text, reminder_html = _reminder_email(student_name, start_msk, for_tutor=True)
                await notify(
                    db, tutor_user.id, NotificationEvent.UPCOMING_REMINDER,
                    "Скоро занятие",
                    f"Занятие с {student_name} начнётся {start_msk:%d.%m.%Y %H:%M} (МСК).",
                    email_html=reminder_html, email_text=reminder_text,
                )
                await system_notification_service.notify(
                    db, tutor_user.id, SystemNotificationEvent.UPCOMING_LESSON_REMINDER,
                    student_name=student_name, time=time_str, lead_minutes=str(tutor_user.reminder_lead_minutes),
                )
                booking.reminder_sent_at = now
                sent += 1

        if booking.student_id is not None and booking.student_reminder_sent_at is None:
            student_user = await db.get(User, booking.student_id)
            if student_user is not None and _is_due(
                start_at, now, student_user.reminder_lead_minutes, tolerance_minutes
            ):
                tutor_profile2 = await db.get(TutorProfile, booking.tutor_id)
                tutor_user2 = await db.get(User, tutor_profile2.user_id) if tutor_profile2 else None
                tutor_name = tutor_user2.display_name if tutor_user2 else "репетитором"
                reminder_text, reminder_html = _reminder_email(tutor_name, start_msk, for_tutor=False)
                await notify(
                    db, student_user.id, NotificationEvent.UPCOMING_REMINDER,
                    "Скоро занятие",
                    f"Занятие с {tutor_name} начнётся {start_msk:%d.%m.%Y %H:%M} (МСК).",
                    email_html=reminder_html, email_text=reminder_text,
                )
                await system_notification_service.notify(
                    db, student_user.id, SystemNotificationEvent.UPCOMING_LESSON_REMINDER,
                    tutor_name=tutor_name, time=time_str, lead_minutes=str(student_user.reminder_lead_minutes),
                )
                booking.student_reminder_sent_at = now
                sent += 1

    if sent:
        await db.commit()
    return sent
