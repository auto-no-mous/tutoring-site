import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import (
    BookingStatus,
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
    SystemNotificationEvent,
)
from app.models.notification import NotificationLog
from app.models.tutor import TutorProfile
from app.models.user import User
from app.services import system_notification_service
from app.services.email_service import send_email
from app.services.schedule_service import MSK
from app.services.telegram_service import send_telegram_message
from app.utils.time import ensure_aware, utcnow

# Cap on Settings' "уведомлять за N минут" field (schemas/user.py) - a week is more
# than generous, and bounds how far ahead send_upcoming_reminders has to scan.
MAX_REMINDER_LEAD_MINUTES = 7 * 24 * 60

logger = logging.getLogger("app.notifications")


async def notify(db: AsyncSession, user_id: uuid.UUID, event_type: NotificationEvent, title: str, body: str) -> None:
    """Dispatches a notification over every channel the user has configured (section
    2.7). Best-effort: failures are logged to NotificationLog and swallowed so a
    misconfigured channel never breaks the calling business operation (booking,
    chat message, etc.)."""
    user = await db.get(User, user_id)
    if user is None:
        return

    if user.telegram_chat_id:
        await _dispatch(db, user.id, NotificationChannel.TELEGRAM, event_type, title, body, user.telegram_chat_id)

    if user.email and user.email_notifications_enabled:
        await _dispatch(db, user.id, NotificationChannel.EMAIL, event_type, title, body, user.email)


async def notify_tutor(
    db: AsyncSession, tutor_id: uuid.UUID, event_type: NotificationEvent, title: str, body: str
) -> None:
    profile = await db.get(TutorProfile, tutor_id)
    if profile is None:
        return
    await notify(db, profile.user_id, event_type, title, body)


async def _dispatch(
    db: AsyncSession,
    user_id: uuid.UUID,
    channel: NotificationChannel,
    event_type: NotificationEvent,
    title: str,
    body: str,
    destination: str,
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
            await send_email(destination, title, body)
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
                await notify(
                    db, tutor_user.id, NotificationEvent.UPCOMING_REMINDER,
                    "Скоро занятие",
                    f"Занятие с {student_name} начнётся {start_msk:%d.%m.%Y %H:%M} (МСК).",
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
                await notify(
                    db, student_user.id, NotificationEvent.UPCOMING_REMINDER,
                    "Скоро занятие",
                    f"Занятие с {tutor_name} начнётся {start_msk:%d.%m.%Y %H:%M} (МСК).",
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
