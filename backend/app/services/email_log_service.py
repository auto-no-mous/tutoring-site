"""Журнал писем: запись фактов отправки/приёма и выборки для админки."""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.email_log import EmailLog
from app.models.enums import EmailDirection, EmailKind, EmailStatus
from app.schemas.email import EmailLogOut, EmailLogPageOut, EmailStatsOut
from app.utils.time import utcnow

logger = logging.getLogger("app.email")

# Тело письма в журнале обрезается: это контроль отправки, а не почтовый ящик.
PREVIEW_LIMIT = 2000
STATS_WINDOW_DAYS = 30


async def record(
    *,
    direction: str,
    kind: str,
    status: str,
    address_from: str,
    address_to: str,
    subject: str,
    body_preview: str = "",
    user_id: uuid.UUID | None = None,
    sent_by_id: uuid.UUID | None = None,
    error: str | None = None,
) -> None:
    """Пишет строку журнала в собственной сессии.

    Своя сессия, а не сессия запроса: письма уходят и оттуда, где сессии нет
    (повторная отправка подтверждения), и запись в журнал не должна попадать в
    транзакцию бизнес-операции - откат регистрации не должен стирать факт
    отправленного письма. Любая ошибка здесь гасится: журнал не может быть
    причиной падения запроса.
    """
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                EmailLog(
                    direction=direction,
                    kind=kind,
                    status=status,
                    address_from=address_from,
                    address_to=address_to,
                    subject=subject[:512],
                    body_preview=body_preview[:PREVIEW_LIMIT],
                    user_id=user_id,
                    sent_by_id=sent_by_id,
                    error=error,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("EMAIL log write failed to=%s subject=%s", address_to, subject)


def _filtered(
    direction: str | None, status: str | None, kind: str | None, query: str | None
) -> Select[tuple[EmailLog]]:
    stmt = select(EmailLog)
    if direction:
        stmt = stmt.where(EmailLog.direction == direction)
    if status:
        stmt = stmt.where(EmailLog.status == status)
    if kind:
        stmt = stmt.where(EmailLog.kind == kind)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(or_(EmailLog.address_to.ilike(like), EmailLog.address_from.ilike(like), EmailLog.subject.ilike(like)))
    return stmt


async def list_page(
    db: AsyncSession,
    *,
    direction: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    query: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> EmailLogPageOut:
    base = _filtered(direction, status, kind, query)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.scalars(
        base.order_by(EmailLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return EmailLogPageOut(
        entries=[EmailLogOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def stats(db: AsyncSession) -> EmailStatsOut:
    now = utcnow()
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=STATS_WINDOW_DAYS)

    async def count(*conditions: object) -> int:
        return await db.scalar(select(func.count()).select_from(EmailLog).where(*conditions)) or 0  # type: ignore[arg-type]

    by_kind_rows = await db.execute(
        select(EmailLog.kind, func.count())
        .where(EmailLog.created_at >= month_ago, EmailLog.status == EmailStatus.SENT.value)
        .group_by(EmailLog.kind)
    )
    return EmailStatsOut(
        sent_24h=await count(EmailLog.created_at >= day_ago, EmailLog.status == EmailStatus.SENT.value),
        failed_24h=await count(EmailLog.created_at >= day_ago, EmailLog.status == EmailStatus.FAILED.value),
        sent_30d=await count(EmailLog.created_at >= month_ago, EmailLog.status == EmailStatus.SENT.value),
        failed_30d=await count(EmailLog.created_at >= month_ago, EmailLog.status == EmailStatus.FAILED.value),
        received_30d=await count(
            EmailLog.created_at >= month_ago, EmailLog.status == EmailStatus.RECEIVED.value
        ),
        by_kind={kind: amount for kind, amount in by_kind_rows.all()},
        last_sent_at=await db.scalar(
            select(func.max(EmailLog.created_at)).where(
                EmailLog.direction == EmailDirection.OUTBOUND.value,
                EmailLog.status == EmailStatus.SENT.value,
            )
        ),
    )


__all__ = ["record", "list_page", "stats", "EmailDirection", "EmailKind", "EmailStatus"]
