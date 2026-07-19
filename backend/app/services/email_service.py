import logging

import aiosmtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("app.email")


async def send_email(to: str, subject: str, body: str) -> None:
    """Sends a plaintext email, or logs it when SMTP isn't configured (local dev)."""
    if not settings.email_enabled or not settings.smtp_host:
        logger.info("EMAIL (not sent, email disabled) to=%s subject=%s\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )


async def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.frontend_base_url}/verify-email?token={token}"
    await send_email(
        to=to,
        subject="Подтверждение почты — it-tutor.pro",
        body=f"Перейдите по ссылке, чтобы подтвердить почту:\n{link}",
    )


async def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.frontend_base_url}/reset-password?token={token}"
    await send_email(
        to=to,
        subject="Восстановление пароля — it-tutor.pro",
        body=f"Перейдите по ссылке, чтобы задать новый пароль:\n{link}",
    )
