"""ops/mail/ingest-mail.py: какой текст письма уходит в журнал админки.

Скрипт живёт не в пакете бэкенда (его запускает Postfix на хосте), поэтому
загружается по пути к файлу."""

import importlib.util
from email import message_from_bytes, policy
from email.message import EmailMessage
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "mail" / "ingest-mail.py"
_spec = importlib.util.spec_from_file_location("ingest_mail", SCRIPT)
assert _spec and _spec.loader
ingest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ingest)


def _parse(message: EmailMessage):
    return message_from_bytes(message.as_bytes(), policy=policy.default)


def test_plain_text_is_kept_whole() -> None:
    msg = EmailMessage()
    msg["Subject"] = "Вопрос"
    body = "Здравствуйте!\n\n" + "строка\n" * 1000 + "https://example.com/x"
    msg.set_content(body)

    text = ingest.body_text(_parse(msg))

    assert text == body.strip()
    assert len(text) > ingest.PREVIEW_LIMIT


def test_html_only_becomes_text_with_link_addresses() -> None:
    msg = EmailMessage()
    msg.set_content(
        "<html><head><style>p{color:red}</style></head><body>"
        "<p>Подтвердите адрес:</p><p><a href='https://spamhaus.example/confirm?t=1'>подтвердить</a></p>"
        "<script>alert(1)</script><div>Спасибо</div></body></html>",
        subtype="html",
    )

    text = ingest.body_text(_parse(msg))

    assert "подтвердить (https://spamhaus.example/confirm?t=1)" in text
    assert "Подтвердите адрес:" in text and "Спасибо" in text
    # Ни разметки, ни стилей, ни скриптов в журнал не попадает.
    assert "<" not in text and "color:red" not in text and "alert" not in text


def test_plain_text_preferred_over_html() -> None:
    msg = EmailMessage()
    msg.set_content("Текстовая версия")
    msg.add_alternative("<p>HTML-версия</p>", subtype="html")

    assert ingest.body_text(_parse(msg)) == "Текстовая версия"


def test_attachments_are_named_not_stored() -> None:
    msg = EmailMessage()
    msg["Subject"] = "Report domain: my-tutor.ru"
    msg.set_content("Отчёт во вложении")
    msg.add_attachment(b"PK\x03\x04", maintype="application", subtype="zip", filename="google.com!my-tutor.ru.zip")

    text = ingest.body_text(_parse(msg))

    assert text.startswith("Отчёт во вложении")
    assert "Вложения (в журнале не сохраняются): google.com!my-tutor.ru.zip" in text
