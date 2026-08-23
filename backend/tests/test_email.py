"""Тесты сборки и отправки транзакционных писем (app.services.email_service)."""

from typing import Any

import pytest

from app.core.config import settings
from app.services import email_service


@pytest.fixture
def smtp_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "mail.example.test")
    monkeypatch.setattr(settings, "smtp_port", 25)
    monkeypatch.setattr(settings, "smtp_user", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    monkeypatch.setattr(settings, "smtp_starttls", False)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Перехватывает вызовы aiosmtplib.send, чтобы тесты не ходили в сеть."""
    calls: list[dict[str, Any]] = []

    async def fake_send(message: Any, **kwargs: Any) -> tuple[dict[str, Any], str]:
        calls.append({"message": message, **kwargs})
        return {}, "250 OK"

    monkeypatch.setattr(email_service.aiosmtplib, "send", fake_send)
    return calls


def test_build_message_has_headers_spam_filters_expect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_from", "no-reply@my-tutor.ru")
    monkeypatch.setattr(settings, "mail_from_name", "my-tutor.ru")
    monkeypatch.setattr(settings, "mail_reply_to", "hello@my-tutor.ru")

    message = email_service.build_message("student@example.com", "Тема", "текст", "<p>html</p>")

    # formataddr берёт имя в кавычки: точка в "my-tutor.ru" - спецсимвол по RFC 5322.
    assert message["From"] == '"my-tutor.ru" <no-reply@my-tutor.ru>'
    assert message["To"] == "student@example.com"
    assert message["Reply-To"] == "hello@my-tutor.ru"
    assert message["Auto-Submitted"] == "auto-generated"
    assert message["Date"]
    # Message-ID должен быть на домене отправителя, а не на hostname контейнера.
    assert message["Message-ID"].endswith("@my-tutor.ru>")


def test_build_message_is_multipart_with_text_fallback() -> None:
    message = email_service.build_message("student@example.com", "Тема", "текстовая версия", "<p>html</p>")

    assert message.is_multipart()
    types = {part.get_content_type() for part in message.walk() if not part.is_multipart()}
    assert types == {"text/plain", "text/html"}
    assert "текстовая версия" in message.get_body(preferencelist=("plain",)).get_content()


def test_build_message_without_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mail_reply_to", None)

    message = email_service.build_message("student@example.com", "Тема", "текст")

    assert message["Reply-To"] is None
    assert not message.is_multipart()


@pytest.mark.asyncio
async def test_send_email_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch, sent: list[dict[str, Any]]) -> None:
    monkeypatch.setattr(settings, "email_enabled", False)

    assert await email_service.send_email("student@example.com", "Тема", "текст") is False
    assert sent == []


@pytest.mark.asyncio
async def test_send_email_omits_auth_for_local_relay(smtp_enabled: None, sent: list[dict[str, Any]]) -> None:
    assert await email_service.send_email("student@example.com", "Тема", "текст") is True

    call = sent[0]
    assert call["hostname"] == "mail.example.test"
    assert call["port"] == 25
    assert call["start_tls"] is False
    # Свой Postfix релеит по адресу сети, без SASL - логин/пароль слать нечем и незачем.
    assert call["username"] is None and call["password"] is None


@pytest.mark.asyncio
async def test_send_email_passes_credentials_when_configured(
    smtp_enabled: None, sent: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "smtp_user", "no-reply@my-tutor.ru")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_starttls", True)

    assert await email_service.send_email("student@example.com", "Тема", "текст") is True

    call = sent[0]
    assert call["username"] == "no-reply@my-tutor.ru"
    assert call["password"] == "secret"
    assert call["start_tls"] is True


@pytest.mark.asyncio
async def test_send_email_swallows_smtp_failure(
    smtp_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*args: Any, **kwargs: Any) -> None:
        raise ConnectionRefusedError("mail server is down")

    monkeypatch.setattr(email_service.aiosmtplib, "send", boom)

    # Упавший почтовый сервер не должен ломать регистрацию или сброс пароля.
    assert await email_service.send_email("student@example.com", "Тема", "текст") is False


@pytest.mark.asyncio
async def test_verification_email_contains_link(smtp_enabled: None, sent: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "frontend_base_url", "https://my-tutor.ru")

    await email_service.send_verification_email("student@example.com", "tok123")

    message = sent[0]["message"]
    assert message["Subject"] == "Подтверждение почты — my-tutor.ru"
    text = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "https://my-tutor.ru/verify-email?token=tok123" in text
    assert "https://my-tutor.ru/verify-email?token=tok123" in html


@pytest.mark.asyncio
async def test_password_reset_email_contains_link(smtp_enabled: None, sent: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "frontend_base_url", "https://my-tutor.ru")

    await email_service.send_password_reset_email("student@example.com", "tok456")

    message = sent[0]["message"]
    assert message["Subject"] == "Восстановление пароля — my-tutor.ru"
    assert "https://my-tutor.ru/reset-password?token=tok456" in message.get_body(preferencelist=("plain",)).get_content()
