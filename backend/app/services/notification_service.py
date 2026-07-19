import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus, NotificationChannel, NotificationEvent, NotificationStatus
from app.models.notification import NotificationLog
from app.models.tutor import TutorProfile
from app.models.user import User
from app.services.email_service import send_email
from app.services.schedule_service import MSK
from app.services.telegram_service import send_telegram_message
from app.utils.time import ensure_aware, utcnow

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


async def send_upcoming_reminders(
    db: AsyncSession, hours_before: float = 24.0, tolerance_minutes: float = 30.0
) -> int:
    """Notifies tutors about individual lessons starting soon (section 2.7). Meant to
    be run periodically (e.g. hourly) by an external scheduler - this codebase doesn't
    wire one up (see app/scripts/send_reminders.py, cron-friendly). A tolerance window
    is used instead of an exact match so it's safe to run on a coarse schedule; each
    booking is only reminded once (reminder_sent_at)."""
    now = utcnow()
    target = now + dt.timedelta(hours=hours_before)
    window_start = target - dt.timedelta(minutes=tolerance_minutes)
    window_end = target + dt.timedelta(minutes=tolerance_minutes)

    result = await db.execute(
        select(Booking).where(
            Booking.status == BookingStatus.SCHEDULED.value,
            Booking.student_id.is_not(None),
            Booking.reminder_sent_at.is_(None),
            Booking.start_at >= window_start,
            Booking.start_at < window_end,
        )
    )
    bookings = list(result.scalars().all())

    for booking in bookings:
        student = await db.get(User, booking.student_id)
        student_name = student.display_name if student else "Ученик"
        start_msk = ensure_aware(booking.start_at).astimezone(MSK)
        await notify_tutor(
            db,
            booking.tutor_id,
            NotificationEvent.UPCOMING_REMINDER,
            "Скоро занятие",
            f"Занятие с {student_name} начнётся {start_msk:%d.%m.%Y %H:%M} (МСК).",
        )
        booking.reminder_sent_at = now

    if bookings:
        await db.commit()
    return len(bookings)
