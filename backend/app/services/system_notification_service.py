import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SystemNotificationEvent, UserRole
from app.models.system_notification import NotificationTemplate, SystemNotification
from app.models.user import User
from app.utils.time import utcnow

# Default Russian-language template text, seeded into notification_templates on first
# use (see ensure_default_templates) and shown as a starting point in the admin UI.
# {placeholders} are filled in via str.format_map at send time - see notify() below.
# A handful of events fire for both roles with different wording (login/welcome);
# the rest only ever have one recipient role, but still get a role-keyed row for a
# consistent admin editing experience.
DEFAULT_TEMPLATES: dict[tuple[SystemNotificationEvent, UserRole], tuple[str, str]] = {
    (SystemNotificationEvent.LOGIN_SUCCESS, UserRole.TUTOR): (
        "Вход в аккаунт",
        "Здравствуйте, {name}! Только что был выполнен вход в ваш аккаунт на it-tutor.pro. "
        "Если это были не вы, срочно смените пароль в разделе «Настройки».",
    ),
    (SystemNotificationEvent.LOGIN_SUCCESS, UserRole.STUDENT): (
        "Вход в аккаунт",
        "Здравствуйте, {name}! Только что был выполнен вход в ваш аккаунт на it-tutor.pro. "
        "Если это были не вы, срочно смените пароль в разделе «Настройки».",
    ),
    (SystemNotificationEvent.LOGIN_FAILED, UserRole.TUTOR): (
        "Неудачная попытка входа",
        "Здравствуйте, {name}! Была зафиксирована неудачная попытка входа в ваш аккаунт "
        "(неверный пароль). Если это были не вы, рекомендуем сменить пароль.",
    ),
    (SystemNotificationEvent.LOGIN_FAILED, UserRole.STUDENT): (
        "Неудачная попытка входа",
        "Здравствуйте, {name}! Была зафиксирована неудачная попытка входа в ваш аккаунт "
        "(неверный пароль). Если это были не вы, рекомендуем сменить пароль.",
    ),
    (SystemNotificationEvent.WELCOME, UserRole.TUTOR): (
        "Добро пожаловать на it-tutor.pro",
        "Добро пожаловать, {name}! Ваш профиль репетитора создан. Заполните раздел «Профиль» "
        "и настройте расписание во вкладке «Расписание», чтобы ученики могли записываться на занятия.",
    ),
    (SystemNotificationEvent.WELCOME, UserRole.STUDENT): (
        "Добро пожаловать на it-tutor.pro",
        "Добро пожаловать, {name}! Теперь вы можете найти репетитора в каталоге и записаться "
        "на первое занятие.",
    ),
    (SystemNotificationEvent.BOOKING_CANCELLED_BY_STUDENT, UserRole.TUTOR): (
        "Ученик отменил занятие",
        "{student_name} отменил(а) занятие {date} в {time} (МСК).",
    ),
    (SystemNotificationEvent.BOOKING_RESCHEDULED_BY_STUDENT, UserRole.TUTOR): (
        "Ученик перенёс занятие",
        "{student_name} перенёс(ла) занятие с {old_date} {old_time} на {new_date} {new_time} (МСК).",
    ),
    (SystemNotificationEvent.GROUP_APPLICATION_RECEIVED, UserRole.TUTOR): (
        "Новая заявка в группу",
        "{student_name} подал(а) заявку на участие в группе «{group_name}». "
        "Рассмотрите её во вкладке «Группы».",
    ),
    (SystemNotificationEvent.GROUP_MEMBER_LEFT, UserRole.TUTOR): (
        "Ученик покинул группу",
        "{student_name} покинул(а) группу «{group_name}».",
    ),
    (SystemNotificationEvent.GROUP_LESSON_NO_SHOW_BY_STUDENT, UserRole.TUTOR): (
        "Ученик не сможет присутствовать",
        "{student_name} сообщил(а), что не сможет присутствовать на групповом занятии "
        "«{group_name}» {date} в {time} (МСК).",
    ),
    (SystemNotificationEvent.BOOKING_CANCELLED_BY_TUTOR, UserRole.STUDENT): (
        "Репетитор отменил занятие",
        "Репетитор отменил ваше занятие {date} в {time} (МСК).",
    ),
    (SystemNotificationEvent.BOOKING_RESCHEDULED_BY_TUTOR, UserRole.STUDENT): (
        "Репетитор перенёс занятие",
        "Репетитор перенёс ваше занятие с {old_date} {old_time} на {new_date} {new_time} (МСК).",
    ),
    (SystemNotificationEvent.GROUP_SCHEDULE_CHANGED, UserRole.STUDENT): (
        "Изменилось расписание группы",
        "Репетитор изменил расписание группы «{group_name}»: ближайшее занятие перенесено "
        "с {old_date} {old_time} на {new_date} {new_time} (МСК).",
    ),
    (SystemNotificationEvent.GROUP_APPLICATION_ACCEPTED, UserRole.STUDENT): (
        "Заявка в группу принята",
        "Ваша заявка на участие в группе «{group_name}» принята репетитором. Добро пожаловать!",
    ),
    (SystemNotificationEvent.GROUP_APPLICATION_REJECTED, UserRole.STUDENT): (
        "Заявка в группу отклонена",
        "Репетитор отклонил вашу заявку на участие в группе «{group_name}».",
    ),
    (SystemNotificationEvent.HOMEWORK_ASSIGNED, UserRole.STUDENT): (
        "Новое домашнее задание",
        "Репетитор задал новое домашнее задание: «{homework_title}». Посмотреть его можно "
        "во вкладке «Домашние задания».",
    ),
    (SystemNotificationEvent.UPCOMING_LESSON_REMINDER, UserRole.TUTOR): (
        "Скоро занятие",
        "Через {lead_minutes} мин ({time}) у вас занятие с {student_name}.",
    ),
    (SystemNotificationEvent.UPCOMING_LESSON_REMINDER, UserRole.STUDENT): (
        "Скоро занятие",
        "Через {lead_minutes} мин ({time}) у вас занятие с репетитором {tutor_name}.",
    ),
}


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def _render(template: str, params: dict) -> str:
    return template.format_map(_SafeDict(params))


async def ensure_default_templates(db: AsyncSession) -> None:
    """Inserts any (event_type, role) template row that doesn't exist yet, using the
    default text above. Idempotent - safe to call on every admin-templates fetch and
    at app startup, so new event types added in later releases get seeded into
    existing databases without a data migration."""
    existing = await db.execute(select(NotificationTemplate.event_type, NotificationTemplate.role))
    existing_keys = {(row[0], row[1]) for row in existing.all()}

    added = False
    for (event, role), (title, body) in DEFAULT_TEMPLATES.items():
        if (event.value, role.value) in existing_keys:
            continue
        db.add(NotificationTemplate(event_type=event.value, role=role.value, title=title, body=body))
        added = True
    if added:
        await db.commit()


async def _get_template(db: AsyncSession, event: SystemNotificationEvent, role: str) -> tuple[str, str]:
    result = await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.event_type == event.value, NotificationTemplate.role == role
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row.title, row.body
    try:
        return DEFAULT_TEMPLATES[(event, UserRole(role))]
    except KeyError:
        return event.value, ""


async def notify(db: AsyncSession, user_id: uuid.UUID, event: SystemNotificationEvent, **params: str) -> None:
    """Creates an in-app "Системные уведомления" notification for `user_id`. Never
    raises on a missing user/template - like notification_service.notify, this must
    not break the calling business operation (booking, login, ...)."""
    user = await db.get(User, user_id)
    if user is None:
        return

    title, body_template = await _get_template(db, event, user.role)
    body = _render(body_template, params)
    db.add(SystemNotification(user_id=user_id, event_type=event.value, title=title, body=body))
    await db.commit()


async def list_for_user(db: AsyncSession, user_id: uuid.UUID, limit: int = 100) -> list[SystemNotification]:
    result = await db.execute(
        select(SystemNotification)
        .where(SystemNotification.user_id == user_id)
        .order_by(SystemNotification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(SystemNotification)
        .where(SystemNotification.user_id == user_id, SystemNotification.read_at.is_(None))
    )
    return result.scalar_one()


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    now = utcnow()
    result = await db.execute(
        select(SystemNotification).where(
            SystemNotification.user_id == user_id, SystemNotification.read_at.is_(None)
        )
    )
    for notification in result.scalars().all():
        notification.read_at = now
    await db.commit()


async def list_templates(db: AsyncSession) -> list[NotificationTemplate]:
    await ensure_default_templates(db)
    result = await db.execute(
        select(NotificationTemplate).order_by(NotificationTemplate.event_type, NotificationTemplate.role)
    )
    return list(result.scalars().all())


async def update_template(db: AsyncSession, template_id: uuid.UUID, title: str, body: str) -> NotificationTemplate:
    template = await db.get(NotificationTemplate, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Шаблон не найден")
    template.title = title
    template.body = body
    await db.commit()
    await db.refresh(template)
    return template
