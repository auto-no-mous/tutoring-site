import pytest

from app.core.config import settings
from app.services import telegram_service


@pytest.fixture(autouse=True)
def _reset_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_service, "_bot", None)
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "123:abc")


def test_bot_talks_to_telegram_directly_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_api_url", None)
    bot = telegram_service._get_bot()
    assert bot is not None
    assert bot.base_url == "https://api.telegram.org/bot123:abc"


def test_bot_goes_through_relay_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_api_url", "https://203.0.113.5/secret/")
    bot = telegram_service._get_bot()
    assert bot is not None
    assert bot.base_url == "https://203.0.113.5/secret/bot123:abc"
    assert bot.base_file_url == "https://203.0.113.5/secret/file/bot123:abc"
