from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.notification import SystemNotificationOut, UnreadSummaryOut
from app.services import chat_service, system_notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/system", response_model=list[SystemNotificationOut])
async def list_system_notifications(current_user: CurrentUser, db: DbSession) -> list[SystemNotificationOut]:
    rows = await system_notification_service.list_for_user(db, current_user.id)
    return [SystemNotificationOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/system/read")
async def mark_system_notifications_read(current_user: CurrentUser, db: DbSession) -> dict[str, bool]:
    await system_notification_service.mark_all_read(db, current_user.id)
    return {"ok": True}


@router.get("/unread-summary", response_model=UnreadSummaryOut)
async def unread_summary(current_user: CurrentUser, db: DbSession) -> UnreadSummaryOut:
    chat_unread = await chat_service.get_total_unread_for_user(db, current_user)
    system_unread = await system_notification_service.unread_count(db, current_user.id)
    return UnreadSummaryOut(chat_unread=chat_unread, system_unread=system_unread, total=chat_unread + system_unread)
