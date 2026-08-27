import datetime as dt
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models.enums import UserRole
from app.models.blog import BlogPost
from app.models.group import Group
from app.models.user import User
from app.schemas.admin import (
    AdminBookingCreate,
    AdminBookingReschedule,
    AdminGroupMemberAdd,
    AdminGroupTutorReassign,
    AdminPasswordReset,
    AdminStudentUpdate,
    AdminTutorUpdate,
)
from app.schemas.blog import BlogPostAdminOut, BlogPostCreate, BlogPostUpdate
from app.schemas.booking import BookingOut, BookingPageOut, BookingTutorUpdate, ManualBookingCreate
from app.schemas.email import (
    AdminEmailSend,
    AdminEmailSendResult,
    EmailLogPageOut,
    EmailStatsOut,
)
from app.schemas.group import (
    GroupApplicationOut,
    GroupMembershipOut,
    GroupOut,
    GroupScheduleSlotOut,
    GroupUpdate,
)
from app.schemas.schedule import SlotOut
from app.schemas.subject import (
    DirectionCreate,
    DirectionOut,
    DirectionUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
)
from app.schemas.notification import NotificationTemplateOut, NotificationTemplateUpdate
from app.schemas.tutor import TutorProfileOut, UploadedImageOut
from app.schemas.user import UserOut
from app.services import (
    admin_service,
    blog_service,
    booking_service,
    email_log_service,
    file_service,
    group_service,
    schedule_service,
    subject_service,
    system_notification_service,
)

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles(UserRole.ADMIN.value))]
)


def _to_group_out(group: Group, member_count: int, duration_minutes: int) -> GroupOut:
    return GroupOut(
        id=group.id,
        tutor_id=group.tutor_id,
        lesson_type_id=group.lesson_type_id,
        name=group.name,
        capacity=group.capacity,
        meeting_link=group.meeting_link,
        is_active=group.is_active,
        schedule_slots=[GroupScheduleSlotOut.model_validate(s, from_attributes=True) for s in group.schedule_slots],
        member_count=member_count,
        created_at=group.created_at,
        duration_minutes=duration_minutes,
    )


# --- Tutors -------------------------------------------------------------------


def _to_profile_out(profile, user: User | None, subjects: list | None = None) -> TutorProfileOut:
    return TutorProfileOut.model_validate(profile, from_attributes=True).model_copy(
        update={
            "display_name": user.display_name if user else None,
            "is_active": user.is_active if user else None,
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "patronymic": user.patronymic if user else None,
            "email": user.email if user else None,
            "email_verified": user.email_verified if user else None,
            "subjects": subjects or [],
        }
    )


@router.get("/tutors", response_model=list[TutorProfileOut])
async def list_tutors(db: DbSession) -> list[TutorProfileOut]:
    profiles = await admin_service.list_tutors(db)
    out = []
    for profile in profiles:
        user = await db.get(User, profile.user_id)
        subject_rows = await subject_service.get_tutor_subjects(db, profile.id)
        out.append(_to_profile_out(profile, user, subject_service.to_tutor_subject_out(subject_rows)))
    return out


@router.get("/tutors/{tutor_id}", response_model=TutorProfileOut)
async def get_tutor(tutor_id: uuid.UUID, db: DbSession) -> TutorProfileOut:
    profile = await admin_service.get_tutor_or_404(db, tutor_id)
    user = await db.get(User, profile.user_id)
    return _to_profile_out(profile, user)


@router.patch("/tutors/{tutor_id}", response_model=TutorProfileOut)
async def update_tutor(tutor_id: uuid.UUID, payload: AdminTutorUpdate, db: DbSession) -> TutorProfileOut:
    profile = await admin_service.get_tutor_or_404(db, tutor_id)
    profile = await admin_service.update_tutor(db, profile, payload)
    user = await db.get(User, profile.user_id)
    return _to_profile_out(profile, user)


@router.delete("/tutors/{tutor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tutor(tutor_id: uuid.UUID, db: DbSession) -> None:
    profile = await admin_service.get_tutor_or_404(db, tutor_id)
    await admin_service.delete_tutor(db, profile)


# --- Students -------------------------------------------------------------------


@router.get("/students", response_model=list[UserOut])
async def list_students(db: DbSession) -> list[UserOut]:
    users = await admin_service.list_students(db)
    return [UserOut.model_validate(u, from_attributes=True) for u in users]


@router.get("/students/{student_id}", response_model=UserOut)
async def get_student(student_id: uuid.UUID, db: DbSession) -> UserOut:
    user = await admin_service.get_student_or_404(db, student_id)
    return UserOut.model_validate(user, from_attributes=True)


@router.patch("/students/{student_id}", response_model=UserOut)
async def update_student(student_id: uuid.UUID, payload: AdminStudentUpdate, db: DbSession) -> UserOut:
    user = await admin_service.get_student_or_404(db, student_id)
    user = await admin_service.update_student(db, user, payload)
    return UserOut.model_validate(user, from_attributes=True)


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: uuid.UUID, db: DbSession) -> None:
    user = await admin_service.get_student_or_404(db, student_id)
    await admin_service.delete_student(db, user)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(user_id: uuid.UUID, payload: AdminPasswordReset, db: DbSession) -> None:
    """Задаёт пользователю новый пароль вместо отправки ссылки на самостоятельный
    сброс - нужна, когда письмо до него не доходит. По user_id, а не отдельными
    ручками для учеников и репетиторов: у TutorProfileOut есть user_id, так что одна
    ручка покрывает обе вкладки админки. Подробности - admin_service."""
    user = await admin_service.get_user_or_404(db, user_id)
    await admin_service.reset_user_password(db, user, payload.new_password)


# --- Bookings (individual lessons) -----------------------------------------------


@router.get("/bookings", response_model=BookingPageOut)
async def list_bookings(
    db: DbSession,
    tutor_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    date_from: dt.datetime | None = None,
    date_to: dt.datetime | None = None,
    subject_id: uuid.UUID | None = None,
    direction_id: uuid.UUID | None = None,
    grade: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> BookingPageOut:
    if page < 1 or not (1 <= page_size <= 100):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректные параметры страницы")
    rows, total = await booking_service.list_all_bookings(
        db,
        tutor_id,
        student_id,
        date_from,
        date_to,
        subject_id=subject_id,
        direction_id=direction_id,
        grade=grade,
        page=page,
        page_size=page_size,
    )
    student_names = await booking_service.get_student_names(db, [r.student_id for r in rows if r.student_id])
    tutor_names = await booking_service.get_tutor_display_names(db, [r.tutor_id for r in rows])
    items = [
        BookingOut.model_validate(r, from_attributes=True).model_copy(
            update={
                "student_display_name": student_names.get(r.student_id) if r.student_id else None,
                "tutor_display_name": tutor_names.get(r.tutor_id),
            }
        )
        for r in rows
    ]
    return BookingPageOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(payload: AdminBookingCreate, db: DbSession) -> BookingOut:
    tutor = await admin_service.get_tutor_or_404(db, payload.tutor_id)
    manual_payload = ManualBookingCreate(
        student_id=payload.student_id,
        lesson_type_id=payload.lesson_type_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        meeting_link=payload.meeting_link,
        notes=payload.notes,
        repeat_weekly=False,
    )
    booking = await booking_service.create_manual_booking(db, tutor, manual_payload)
    return BookingOut.model_validate(booking, from_attributes=True)


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
async def update_booking(booking_id: uuid.UUID, payload: BookingTutorUpdate, db: DbSession) -> BookingOut:
    booking = await booking_service.get_booking_or_404(db, booking_id)
    booking = await booking_service.update_booking_by_tutor(db, booking, payload)
    return BookingOut.model_validate(booking, from_attributes=True)


@router.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(booking_id: uuid.UUID, db: DbSession) -> None:
    booking = await booking_service.get_booking_or_404(db, booking_id)
    await booking_service.delete_booking(db, booking)


@router.get("/bookings/{booking_id}/reschedule/dates", response_model=list[dt.date])
async def get_admin_reschedule_dates(
    booking_id: uuid.UUID, date_from: dt.date, date_to: dt.date, db: DbSession, duration_minutes: int | None = None
) -> list[dt.date]:
    if (date_to - date_from).days > 60:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Слишком большой диапазон дат")
    booking = await booking_service.get_booking_or_404(db, booking_id)
    tutor, default_duration = await booking_service.get_admin_reschedule_context(db, booking)
    return await schedule_service.compute_available_dates_by_duration(
        db,
        tutor,
        duration_minutes or default_duration,
        date_from,
        date_to,
        exclude_booking_id=booking.id,
        ignore_lead_time=True,
    )


@router.get("/bookings/{booking_id}/reschedule/slots", response_model=list[SlotOut])
async def get_admin_reschedule_slots(
    booking_id: uuid.UUID, date: dt.date, db: DbSession, duration_minutes: int | None = None
) -> list[SlotOut]:
    booking = await booking_service.get_booking_or_404(db, booking_id)
    tutor, default_duration = await booking_service.get_admin_reschedule_context(db, booking)
    return await schedule_service.compute_day_slots_by_duration(
        db, tutor, duration_minutes or default_duration, date, exclude_booking_id=booking.id, ignore_lead_time=True
    )


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingOut)
async def reschedule_booking(booking_id: uuid.UUID, payload: AdminBookingReschedule, db: DbSession) -> BookingOut:
    booking = await booking_service.get_booking_or_404(db, booking_id)
    new_booking = await booking_service.admin_reschedule_booking(
        db, booking, payload.new_start_at, payload.duration_minutes
    )
    names = await booking_service.get_student_names(db, [new_booking.student_id] if new_booking.student_id else [])
    return BookingOut.model_validate(new_booking, from_attributes=True).model_copy(
        update={"student_display_name": names.get(new_booking.student_id) if new_booking.student_id else None}
    )


# --- Groups, applications, membership --------------------------------------------


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(db: DbSession) -> list[GroupOut]:
    groups = await group_service.list_all_groups(db)
    out = []
    for group in groups:
        count = await group_service.count_active_members(db, group.id)
        duration = await group_service.get_lesson_type_duration(db, group.lesson_type_id)
        out.append(_to_group_out(group, count, duration))
    return out


@router.patch("/groups/{group_id}", response_model=GroupOut)
async def update_group(group_id: uuid.UUID, payload: GroupUpdate, db: DbSession) -> GroupOut:
    group = await group_service.get_group_or_404(db, group_id)
    group = await group_service.update_group(db, group, payload)
    count = await group_service.count_active_members(db, group.id)
    duration = await group_service.get_lesson_type_duration(db, group.lesson_type_id)
    return _to_group_out(group, count, duration)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, db: DbSession) -> None:
    group = await group_service.get_group_or_404(db, group_id)
    await db.delete(group)
    await db.commit()


@router.post("/groups/{group_id}/reassign-tutor", response_model=GroupOut)
async def reassign_group_tutor(group_id: uuid.UUID, payload: AdminGroupTutorReassign, db: DbSession) -> GroupOut:
    group = await group_service.get_group_or_404(db, group_id)
    await admin_service.get_tutor_or_404(db, payload.tutor_id)
    group = await group_service.admin_reassign_tutor(db, group, payload.tutor_id, payload.lesson_type_id)
    count = await group_service.count_active_members(db, group.id)
    duration = await group_service.get_lesson_type_duration(db, group.lesson_type_id)
    return _to_group_out(group, count, duration)


@router.get("/groups/{group_id}/applications", response_model=list[GroupApplicationOut])
async def list_applications(group_id: uuid.UUID, db: DbSession) -> list[GroupApplicationOut]:
    await group_service.get_group_or_404(db, group_id)
    rows = await group_service.list_applications(db, group_id)
    return [GroupApplicationOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/groups/{group_id}/applications/{application_id}/accept", response_model=GroupMembershipOut)
async def accept_application(group_id: uuid.UUID, application_id: uuid.UUID, db: DbSession) -> GroupMembershipOut:
    group = await group_service.get_group_or_404(db, group_id)
    application = await group_service.get_application_or_404(db, application_id)
    if application.group_id != group.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    membership = await group_service.accept_application(db, group, application)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


@router.post("/groups/{group_id}/applications/{application_id}/reject", response_model=GroupApplicationOut)
async def reject_application(group_id: uuid.UUID, application_id: uuid.UUID, db: DbSession) -> GroupApplicationOut:
    group = await group_service.get_group_or_404(db, group_id)
    application = await group_service.get_application_or_404(db, application_id)
    if application.group_id != group.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    application = await group_service.reject_application(db, application)
    return GroupApplicationOut.model_validate(application, from_attributes=True)


@router.get("/groups/{group_id}/members", response_model=list[GroupMembershipOut])
async def list_members(group_id: uuid.UUID, db: DbSession) -> list[GroupMembershipOut]:
    await group_service.get_group_or_404(db, group_id)
    rows = await group_service.list_members(db, group_id)
    return [GroupMembershipOut.model_validate(r, from_attributes=True) for r in rows]


@router.delete("/groups/{group_id}/members/{student_id}", response_model=GroupMembershipOut)
async def remove_member(group_id: uuid.UUID, student_id: uuid.UUID, db: DbSession) -> GroupMembershipOut:
    group = await group_service.get_group_or_404(db, group_id)
    membership = await group_service.admin_remove_member(db, group, student_id)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


@router.post("/groups/{group_id}/members", response_model=GroupMembershipOut, status_code=status.HTTP_201_CREATED)
async def add_member(group_id: uuid.UUID, payload: AdminGroupMemberAdd, db: DbSession) -> GroupMembershipOut:
    group = await group_service.get_group_or_404(db, group_id)
    membership = await group_service.admin_add_member(db, group, payload.student_id)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


# --- Subjects/directions (controlled vocabulary, section 10 redesign) -------------


@router.get("/subjects", response_model=list[SubjectOut])
async def list_subjects(db: DbSession) -> list[SubjectOut]:
    rows = await subject_service.list_subjects(db)
    return [SubjectOut.model_validate(s, from_attributes=True) for s in rows]


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
async def create_subject(payload: SubjectCreate, db: DbSession) -> SubjectOut:
    subject = await subject_service.create_subject(db, payload)
    return SubjectOut.model_validate(subject, from_attributes=True)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
async def update_subject(subject_id: uuid.UUID, payload: SubjectUpdate, db: DbSession) -> SubjectOut:
    subject = await subject_service.get_subject_or_404(db, subject_id)
    subject = await subject_service.update_subject(db, subject, payload)
    return SubjectOut.model_validate(subject, from_attributes=True)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: uuid.UUID, db: DbSession) -> None:
    subject = await subject_service.get_subject_or_404(db, subject_id)
    await subject_service.delete_subject(db, subject)


@router.post("/subjects/{subject_id}/directions", response_model=DirectionOut, status_code=status.HTTP_201_CREATED)
async def create_direction(subject_id: uuid.UUID, payload: DirectionCreate, db: DbSession) -> DirectionOut:
    subject = await subject_service.get_subject_or_404(db, subject_id)
    direction = await subject_service.create_direction(db, subject, payload.name)
    return DirectionOut.model_validate(direction, from_attributes=True)


@router.patch("/directions/{direction_id}", response_model=DirectionOut)
async def update_direction(direction_id: uuid.UUID, payload: DirectionUpdate, db: DbSession) -> DirectionOut:
    direction = await subject_service.get_direction_or_404(db, direction_id)
    direction = await subject_service.update_direction(db, direction, payload.name)
    return DirectionOut.model_validate(direction, from_attributes=True)


@router.delete("/directions/{direction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_direction(direction_id: uuid.UUID, db: DbSession) -> None:
    direction = await subject_service.get_direction_or_404(db, direction_id)
    await subject_service.delete_direction(db, direction)


# --- Notification templates ----------------------------------------------------


@router.get("/notification-templates", response_model=list[NotificationTemplateOut])
async def list_notification_templates(db: DbSession) -> list[NotificationTemplateOut]:
    templates = await system_notification_service.list_templates(db)
    return [NotificationTemplateOut.model_validate(t, from_attributes=True) for t in templates]


@router.put("/notification-templates/{template_id}", response_model=NotificationTemplateOut)
async def update_notification_template(
    template_id: uuid.UUID, payload: NotificationTemplateUpdate, db: DbSession
) -> NotificationTemplateOut:
    template = await system_notification_service.update_template(db, template_id, payload.title, payload.body)
    return NotificationTemplateOut.model_validate(template, from_attributes=True)


# --- Почта ------------------------------------------------------------------
# Журнал писем и отправка писем пользователям руками. Входящие письма попадают
# сюда через ops/mail/ingest-mail.py (Postfix отдаёт их бэкенду), см. ops/mail/README.md.


@router.get("/emails/stats", response_model=EmailStatsOut)
async def email_stats(db: DbSession) -> EmailStatsOut:
    return await email_log_service.stats(db)


@router.get("/emails", response_model=EmailLogPageOut)
async def list_emails(
    db: DbSession,
    direction: str | None = None,
    kind: str | None = None,
    # alias, потому что имя status в этом модуле занято fastapi.status.
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> EmailLogPageOut:
    return await email_log_service.list_page(
        db, direction=direction, status=status_filter, kind=kind, query=q, page=page, page_size=page_size
    )


@router.post("/emails/send", response_model=AdminEmailSendResult)
async def send_emails(payload: AdminEmailSend, db: DbSession, admin: CurrentUser) -> AdminEmailSendResult:
    return await admin_service.send_emails(db, payload, admin)


# --- Blog ------------------------------------------------------------------------


def _to_blog_admin_out(post: BlogPost, author_name: str | None) -> BlogPostAdminOut:
    return BlogPostAdminOut.model_validate(post, from_attributes=True).model_copy(
        update={"author_name": author_name}
    )


@router.get("/blog", response_model=list[BlogPostAdminOut])
async def list_blog_posts(db: DbSession) -> list[BlogPostAdminOut]:
    """Unlike the public listing, includes drafts and carries the full body - the admin
    table doubles as the edit form's data source."""
    posts = await blog_service.list_admin_posts(db)
    authors = await blog_service.get_author_names(db, posts)
    return [_to_blog_admin_out(p, authors.get(p.author_id) if p.author_id else None) for p in posts]


@router.post("/blog", response_model=BlogPostAdminOut, status_code=status.HTTP_201_CREATED)
async def create_blog_post(payload: BlogPostCreate, admin: CurrentUser, db: DbSession) -> BlogPostAdminOut:
    post = await blog_service.create_post(db, payload, admin.id)
    return _to_blog_admin_out(post, admin.display_name)


@router.patch("/blog/{post_id}", response_model=BlogPostAdminOut)
async def update_blog_post(post_id: uuid.UUID, payload: BlogPostUpdate, db: DbSession) -> BlogPostAdminOut:
    post = await blog_service.get_post_or_404(db, post_id)
    post = await blog_service.update_post(db, post, payload)
    authors = await blog_service.get_author_names(db, [post])
    return _to_blog_admin_out(post, authors.get(post.author_id) if post.author_id else None)


@router.delete("/blog/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog_post(post_id: uuid.UUID, db: DbSession) -> None:
    post = await blog_service.get_post_or_404(db, post_id)
    await blog_service.delete_post(db, post)


@router.post("/blog/images", response_model=UploadedImageOut)
async def upload_blog_image(file: UploadFile = File(...)) -> UploadedImageOut:
    """Images for the article body and covers. Saved under the same /files mount the
    rich-text sanitizers allow-list as an image source (see utils/html_sanitize.py)."""
    url = await file_service.save_upload(file, "blog-images", file_service.ALLOWED_IMAGE_TYPES)
    return UploadedImageOut(url=url)
