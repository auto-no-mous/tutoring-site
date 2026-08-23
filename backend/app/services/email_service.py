import logging
import uuid
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr

import aiosmtplib

from app.core.config import settings
from app.models.enums import EmailDirection, EmailKind, EmailStatus
from app.services import email_log_service
from app.services.email_templates import render_email, render_notice_email

logger = logging.getLogger("app.email")


def _sender_domain() -> str:
    """Домен из SMTP_FROM — нужен для Message-ID, иначе туда попадёт имя контейнера."""
    _, address = parseaddr(settings.smtp_from)
    _, _, domain = address.partition("@")
    return domain or "my-tutor.ru"


def build_message(to: str, subject: str, text_body: str, html_body: str | None = None) -> EmailMessage:
    """Собирает письмо со всеми заголовками, которые ждут антиспам-фильтры.

    Date и Message-ID Postfix проставил бы и сам, но письмо, пришедшее к нему уже
    полным, одинаково выглядит и при отправке через внешний SMTP. Auto-Submitted
    (RFC 3834) гасит автоответы вроде "меня нет в офисе" на no-reply@.
    """
    message = EmailMessage()
    message["From"] = formataddr((settings.mail_from_name, settings.smtp_from))
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=_sender_domain())
    message["Auto-Submitted"] = "auto-generated"
    if settings.mail_reply_to:
        message["Reply-To"] = settings.mail_reply_to
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


async def send_email(
    to: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    *,
    kind: str = EmailKind.OTHER.value,
    user_id: uuid.UUID | None = None,
    sent_by_id: uuid.UUID | None = None,
) -> bool:
    """Отправляет письмо. Возвращает True, если оно ушло.

    Ошибки SMTP не пробрасываются наверх: письмо — побочный эффект регистрации или
    сброса пароля, и падение почтового сервера не должно превращаться в 500 для
    пользователя. Неудача пишется в лог, пользователь может нажать "отправить ещё раз".
    """
    if not settings.email_enabled or not settings.smtp_host:
        logger.info("EMAIL (not sent, email disabled) to=%s subject=%s\n%s", to, subject, body)
        return False

    message = build_message(to, subject, body, html_body)
    # Свой Postfix релеит по адресу сети, без SASL: логин имеет смысл только для
    # внешнего SMTP, и только когда заданы обе половины пары. None = не авторизуемся.
    use_auth = bool(settings.smtp_user and settings.smtp_password)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user if use_auth else None,
            password=settings.smtp_password if use_auth else None,
            # Ровно True/False, не None: None у aiosmtplib означает "STARTTLS, если
            # сервер его предлагает", а свой Postfix его предлагает — и проверка
            # сертификата упадёт на несовпадении имени (host.docker.internal).
            start_tls=settings.smtp_starttls,
            timeout=settings.smtp_timeout_seconds,
        )
    except Exception as exc:
        logger.exception("EMAIL send failed to=%s subject=%s", to, subject)
        await email_log_service.record(
            direction=EmailDirection.OUTBOUND.value,
            kind=kind,
            status=EmailStatus.FAILED.value,
            address_from=settings.smtp_from,
            address_to=to,
            subject=subject,
            body_preview=body,
            user_id=user_id,
            sent_by_id=sent_by_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return False

    logger.info("EMAIL sent to=%s subject=%s", to, subject)
    await email_log_service.record(
        direction=EmailDirection.OUTBOUND.value,
        kind=kind,
        status=EmailStatus.SENT.value,
        address_from=settings.smtp_from,
        address_to=to,
        subject=subject,
        body_preview=body,
        user_id=user_id,
        sent_by_id=sent_by_id,
    )
    return True


async def send_verification_email(to: str, token: str, user_id: uuid.UUID | None = None) -> bool:
    link = f"{settings.frontend_base_url}/verify-email?token={token}"
    text, html = render_email(
        heading="Подтвердите почту",
        intro="Вы зарегистрировались на my-tutor.ru. Остался один шаг — подтвердите адрес почты.",
        button_label="Подтвердить почту",
        button_url=link,
        note="Ссылка действует ограниченное время. Если она перестанет работать, запросите новую в настройках профиля.",
    )
    return await send_email(
        to=to,
        subject="Подтверждение почты — my-tutor.ru",
        body=text,
        html_body=html,
        kind=EmailKind.VERIFICATION.value,
        user_id=user_id,
    )


async def send_password_reset_email(to: str, token: str, user_id: uuid.UUID | None = None) -> bool:
    link = f"{settings.frontend_base_url}/reset-password?token={token}"
    text, html = render_email(
        heading="Восстановление пароля",
        intro="Мы получили запрос на смену пароля к вашему аккаунту на my-tutor.ru.",
        button_label="Задать новый пароль",
        button_url=link,
        note="Если вы не запрашивали смену пароля, ничего делать не нужно — пароль останется прежним.",
    )
    return await send_email(
        to=to,
        subject="Восстановление пароля — my-tutor.ru",
        body=text,
        html_body=html,
        kind=EmailKind.PASSWORD_RESET.value,
        user_id=user_id,
    )


async def send_admin_email(
    to: str, subject: str, body: str, *, sent_by_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> bool:
    """Письмо, написанное руками из админки. Тема идёт в письмо как есть, текст -
    в фирменный шаблон без кнопки."""
    text, html = render_notice_email(heading=subject, body_text=body)
    return await send_email(
        to=to,
        subject=subject,
        body=text,
        html_body=html,
        kind=EmailKind.ADMIN.value,
        user_id=user_id,
        sent_by_id=sent_by_id,
    )
