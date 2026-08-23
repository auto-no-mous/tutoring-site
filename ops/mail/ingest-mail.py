#!/usr/bin/env python3
"""Отдаёт входящее письмо бэкенду, чтобы оно попало в журнал почты админки.

Postfix передаёт сюда письмо целиком на stdin (см. алиас mailingest в
ops/mail/install.sh). Скрипт разбирает конверт, берёт превью текста и делает
POST на /api/v1/mail/inbound с общим секретом.

Письмо при этом всё равно пересылается на личный ящик администратора - это
только копия для статистики, поэтому скрипт ВСЕГДА завершается с кодом 0:
недоступный бэкенд не должен превращаться в отбойник для отправителя.
"""

import json
import sys
import urllib.error
import urllib.request
from email import message_from_binary_file, policy
from email.header import decode_header, make_header
from email.utils import parseaddr
from pathlib import Path

API_URL = "https://my-tutor.ru/api/v1/mail/inbound"
TOKEN_FILE = Path("/etc/my-tutor-mail-ingest.token")
PREVIEW_LIMIT = 2000
TIMEOUT_SECONDS = 10


def decoded(value: str | None) -> str:
    """Заголовки часто приходят в MIME-кодировке (=?utf-8?B?...?=)."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def text_preview(message) -> str:
    """Первая текстовая часть письма, обрезанная до PREVIEW_LIMIT."""
    part = message.get_body(preferencelist=("plain", "html")) if hasattr(message, "get_body") else None
    if part is None:
        for candidate in message.walk():
            if candidate.get_content_type() == "text/plain":
                part = candidate
                break
    if part is None:
        return ""
    try:
        payload = part.get_content()
    except Exception:
        raw = part.get_payload(decode=True) or b""
        payload = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
    return payload.strip()[:PREVIEW_LIMIT]


def main() -> int:
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"ingest-mail: не прочитать токен: {exc}", file=sys.stderr)
        return 0

    try:
        # policy.default даёт EmailMessage с get_body()/get_content() и сам
        # раскодирует заголовки; без него пришёл бы legacy-Message.
        message = message_from_binary_file(sys.stdin.buffer, policy=policy.default)
        payload = {
            "address_from": parseaddr(decoded(message.get("From")))[1] or "unknown",
            "address_to": parseaddr(decoded(message.get("To")))[1] or "unknown",
            "subject": decoded(message.get("Subject"))[:512],
            "body_preview": text_preview(message),
        }
    except Exception as exc:
        print(f"ingest-mail: не разобрать письмо: {exc}", file=sys.stderr)
        return 0

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Mail-Ingest-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            response.read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"ingest-mail: бэкенд недоступен: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
