"""Приём входящих писем от почтового сервера.

Postfix отдаёт копию каждого входящего письма скрипту ops/mail/ingest-mail.py, а
тот вызывает этот эндпоинт - так входящие видны в журнале почты админки. Само
письмо на info@ по-прежнему пересылается на личный ящик администратора, а для
служебных адресов журнал - единственная копия; здесь хранится конверт и текст
письма (без HTML и вложений, только их имена).

Эндпоинт не в /admin: ходит в него машина, а не человек с JWT. Авторизация -
общий секрет в заголовке (MAIL_INGEST_TOKEN), тот же файл лежит на хосте у
скрипта. Пока токен не задан, ручка отключена совсем.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.enums import EmailDirection, EmailKind, EmailStatus
from app.services import email_log_service

router = APIRouter(prefix="/mail", tags=["mail"])


class InboundEmailIn(BaseModel):
    address_from: str = Field(max_length=320)
    address_to: str = Field(max_length=320)
    subject: str = Field(default="", max_length=512)
    body_preview: str = Field(default="", max_length=email_log_service.PREVIEW_LIMIT)
    # Весь текст письма. Необязателен: прежняя версия ops/mail/ingest-mail.py слала
    # только превью, и после обновления бэкенда она не должна начать получать 422.
    body_text: str | None = Field(default=None, max_length=email_log_service.BODY_TEXT_LIMIT)


@router.post("/inbound", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_inbound_email(
    payload: InboundEmailIn,
    x_mail_ingest_token: Annotated[str | None, Header()] = None,
) -> None:
    token = settings.mail_ingest_token
    # compare_digest, а не ==: сравнение за постоянное время не даёт подобрать
    # токен по времени ответа.
    if not token or not x_mail_ingest_token or not hmac.compare_digest(x_mail_ingest_token, token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный токен")

    await email_log_service.record(
        direction=EmailDirection.INBOUND.value,
        kind=EmailKind.INBOUND.value,
        status=EmailStatus.RECEIVED.value,
        address_from=payload.address_from,
        address_to=payload.address_to,
        subject=payload.subject,
        body_preview=payload.body_preview,
        body_text=payload.body_text,
    )
