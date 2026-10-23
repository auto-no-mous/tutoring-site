#!/usr/bin/env python3
"""Отдаёт входящее письмо бэкенду, чтобы оно попало в журнал почты админки.

Postfix передаёт сюда письмо целиком на stdin (см. алиас mailingest в
ops/mail/install.sh). Скрипт разбирает конверт, достаёт текст письма и делает
POST на /api/v1/mail/inbound с общим секретом.

Текст передаётся целиком (body_text) и отдельно - начало для списка (body_preview).
Если у письма нет текстовой версии, только HTML, он переводится в текст здесь же,
адреса ссылок сохраняются в скобках: админка чужой HTML не отображает (иначе письмо
могло бы выполнить скрипт в её браузере), показывает только текст. Вложения не
передаются - только их имена в конце текста.

Скрипт ВСЕГДА завершается с кодом 0: недоступный бэкенд не должен превращаться в
отбойник для отправителя.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from email import message_from_binary_file, policy
from email.header import decode_header, make_header
from email.utils import parseaddr
from html.parser import HTMLParser
from pathlib import Path

API_URL = "https://my-tutor.ru/api/v1/mail/inbound"
TOKEN_FILE = Path("/etc/my-tutor-mail-ingest.token")
PREVIEW_LIMIT = 2000
BODY_TEXT_LIMIT = 200_000
TIMEOUT_SECONDS = 10


def decoded(value: str | None) -> str:
    """Заголовки часто приходят в MIME-кодировке (=?utf-8?B?...?=)."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


class _HtmlToText(HTMLParser):
    """HTML письма в читаемый текст: блоки - с новой строки, у ссылки - её адрес в
    скобках, стили и скрипты выбрасываются. Без сторонних библиотек: скрипт
    запускается системным python3 на хосте, а не в окружении бэкенда."""

    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "hr", "blockquote"}
    SKIP = {"style", "script", "head", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._link_text = []

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "a" and self._href:
            text = "".join(self._link_text).strip()
            if re.match(r"^(https?:|mailto:)", self._href) and self._href not in text:
                self.parts.append(f" ({self._href})")
            self._href = None

    def handle_data(self, data):
        if self._skip:
            return
        text = re.sub(r"\s+", " ", data)
        self.parts.append(text)
        if self._href is not None:
            self._link_text.append(text)


def html_to_text(html: str) -> str:
    parser = _HtmlToText()
    parser.feed(html)
    parser.close()
    lines = [line.strip() for line in "".join(parser.parts).split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _part_text(part) -> str:
    try:
        return part.get_content()
    except Exception:
        raw = part.get_payload(decode=True) or b""
        return raw.decode(part.get_content_charset() or "utf-8", errors="replace")


def body_text(message) -> str:
    """Весь текст письма: текстовая версия, а если её нет - HTML, переведённый в
    текст. В конце - имена вложений (сами вложения в журнал не попадают)."""
    text = ""
    part = message.get_body(preferencelist=("plain", "html")) if hasattr(message, "get_body") else None
    if part is not None:
        content = _part_text(part)
        text = html_to_text(content) if part.get_content_type() == "text/html" else content.strip()
    else:
        for candidate in message.walk():
            if candidate.get_content_type() == "text/plain":
                text = _part_text(candidate).strip()
                break

    names = []
    if hasattr(message, "iter_attachments"):
        names = [a.get_filename() or a.get_content_type() for a in message.iter_attachments()]
    if names:
        text = (text + "\n\n" if text else "") + "Вложения (в журнале не сохраняются): " + ", ".join(names)
    return text[:BODY_TEXT_LIMIT]


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
        }
        text = body_text(message)
        payload["body_preview"] = text[:PREVIEW_LIMIT]
        payload["body_text"] = text
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
