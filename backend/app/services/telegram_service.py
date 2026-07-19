import logging

from telegram import Bot
from telegram.error import TelegramError

from app.core.config import settings

logger = logging.getLogger("app.telegram")

_bot: Bot | None = None


def _get_bot() -> Bot | None:
    global _bot
    if not settings.telegram_enabled or not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def send_telegram_message(chat_id: str, text: str) -> None:
    """Sends a Telegram message, or logs it when the bot isn't configured (local dev)."""
    bot = _get_bot()
    if bot is None:
        logger.info("TELEGRAM (not sent, disabled) to=%s\n%s", chat_id, text)
        return

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramError as exc:
        logger.warning("Telegram send failed to=%s: %s", chat_id, exc)
        raise
